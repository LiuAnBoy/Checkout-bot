"""Wait for sale time, then fire /cart/add workers and verify with /cart.json."""

import threading
import time
from typing import Any

import requests

from .config import (
    BACKOFF_429_MS,
    FIRE_INTERVAL_MS,
    MAX_ATTEMPTS_PER_VARIANT,
    OVERALL_TIMEOUT_S,
)
from .logger import get_logger
from .menu import Product
from .sync import fetch_variant_id

BASE_URL = "https://www.rayyatreats.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000.0)


def _now_ts() -> float:
    return time.monotonic()


def _cart_json(session: requests.Session) -> dict[str, Any]:
    resp = session.get(f"{BASE_URL}/cart.json", timeout=5)
    return resp.json()


def _add_to_cart(
    session: requests.Session,
    csrf_token: str,
    variant_id: int,
    quantity: int = 1,
) -> tuple[int, int | None]:
    """Single POST /cart/add. Returns (HTTP status, line-item quantity or None).

    The 200 response body echoes the resulting cart line item, including its
    ``quantity``. We surface that so the caller can confirm the server honored
    the requested quantity rather than silently capping it at 1.
    """
    resp = session.post(
        f"{BASE_URL}/cart/add",
        data={"id": variant_id, "quantity": quantity},
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        },
        timeout=5,
    )
    line_qty: int | None = None
    if resp.status_code == 200:
        try:
            line_qty = resp.json().get("quantity")
        except ValueError:
            line_qty = None
    return resp.status_code, line_qty


# ---------------------------------------------------------------------------
# Fire + Verify loops
# ---------------------------------------------------------------------------


def _fire_worker(
    session: requests.Session,
    csrf_token: str,
    product: Product,
    variant_id: int,
    stop_event: threading.Event,
    success_event: threading.Event,
) -> None:
    """Per-variant fire loop: POST /cart/add at FIRE_INTERVAL_MS until done.

    POSTs the full ``product.quantity`` in a single request and sets
    ``success_event`` on HTTP 200 (the response echoes the line-item quantity)
    or HTTP 409 (限購, already in the cart).
    """
    attempts = 0
    backoff_idx = 0
    vid = variant_id
    refetched = False
    status_counts: dict[int, int] = {}
    target_qty = max(1, product.quantity)
    log = get_logger()

    while not stop_event.is_set() and attempts < MAX_ATTEMPTS_PER_VARIANT:
        try:
            status, line_qty = _add_to_cart(session, csrf_token, vid, target_qty)
        except Exception as e:
            print(f"\n   ⚠️  {product.name}：請求例外 ({e!r})")
            _sleep_ms(FIRE_INTERVAL_MS)
            continue

        attempts += 1
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == 200:
            # Authoritative success — POST returned the line item.
            qty_note = f"，數量 {line_qty}" if line_qty is not None else ""
            print(
                f"\n   ✅ {product.name}：HTTP 200 第 {attempts} 次成功"
                f"（要求 {target_qty}{qty_note}）"
            )
            if line_qty is not None and line_qty < target_qty:
                print(
                    f"   ⚠️  {product.name}：伺服器只加入 {line_qty}/{target_qty}，"
                    "可能受限購限制"
                )
            log.info(
                "成功 handle=%s vid=%s attempts=%d line_qty=%s target=%d",
                product.handle, vid, attempts, line_qty, target_qty,
            )
            success_event.set()
            return

        if status == 409:
            # 限購 — items are already in the cart, treat as success.
            print(f"\n   ✅ {product.name}：HTTP 409（已達限購＝已在購物車中）")
            log.info("409 限購視為成功 handle=%s vid=%s attempts=%d", product.handle, vid, attempts)
            success_event.set()
            return

        if status in (404, 422) and not refetched:
            refetched = True
            fresh = fetch_variant_id(session, product.handle)
            if fresh and fresh != vid:
                print(f"\n   🔄 {product.name}：variant {vid}→{fresh}（just-fetched），重試")
                log.warning("variant 重抓 handle=%s %s→%s status=%s", product.handle, vid, fresh, status)
                vid = fresh
            else:
                print(f"\n   ⚠️  {product.name}：{status}，variant_id 未變，繼續重試")
                log.warning("variant 重抓無變化 handle=%s vid=%s status=%s", product.handle, vid, status)
            _sleep_ms(FIRE_INTERVAL_MS)
        elif status == 429:
            delay = BACKOFF_429_MS[min(backoff_idx, len(BACKOFF_429_MS) - 1)]
            print(f"\n   ⏳ {product.name}：HTTP 429 → backoff {delay}ms")
            backoff_idx += 1
            _sleep_ms(delay)
        else:
            print(f"\n   ⚠️  {product.name}：HTTP {status}（第 {attempts} 次）")
            backoff_idx = 0
            _sleep_ms(FIRE_INTERVAL_MS)

    if attempts >= MAX_ATTEMPTS_PER_VARIANT and not stop_event.is_set():
        breakdown = ", ".join(f"{s}×{n}" for s, n in sorted(status_counts.items()))
        print(f"   ⚠️  {product.name}：已達最大嘗試次數 ({MAX_ATTEMPTS_PER_VARIANT})；status={breakdown}")
        log.warning(
            "達最大嘗試 handle=%s vid=%s attempts=%d status=%s",
            product.handle, vid, attempts, breakdown,
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def fire(
    session: requests.Session,
    csrf_token: str,
    selected: list[Product],
) -> tuple[list[Product], list[Product]]:
    """Fire /cart/add workers immediately and verify with /cart.json.

    Args:
        session: Authenticated requests.Session.
        csrf_token: CSRF token for POST requests.
        selected: Products the user wants to buy.

    Returns:
        (succeeded, failed) lists of Products.
    """
    print("\n🚀 開始搶購！")

    # Collect all variants (one worker per variant)
    variant_map: dict[int, Product] = {}
    for p in selected:
        for v in p.variants:
            variant_map[v["id"]] = p

    # Events
    global_stop = threading.Event()
    per_variant_stops: dict[int, threading.Event] = {
        vid: threading.Event() for vid in variant_map
    }

    # Merge per-variant stop into worker stop event
    combined_stops: dict[int, threading.Event] = {}
    for vid in variant_map:
        combined = threading.Event()

        def _watch(g: threading.Event, pv: threading.Event, c: threading.Event) -> None:
            while not g.is_set() and not pv.is_set():
                time.sleep(0.05)
            c.set()

        t = threading.Thread(
            target=_watch,
            args=(global_stop, per_variant_stops[vid], combined),
            daemon=True,
        )
        t.start()
        combined_stops[vid] = combined

    # Launch fire workers
    fire_threads = []
    for vid, product in variant_map.items():
        t = threading.Thread(
            target=_fire_worker,
            args=(
                session,
                csrf_token,
                product,
                vid,
                combined_stops[vid],
                per_variant_stops[vid],
            ),
            daemon=True,
        )
        t.start()
        fire_threads.append(t)

    # Wait for either all per_variant_stops to be set (= all workers succeeded)
    # or the overall timeout. cart.json is unreliable for member carts on this
    # storefront, so we trust the per-variant success signal from workers.
    deadline = time.monotonic() + OVERALL_TIMEOUT_S
    while time.monotonic() < deadline:
        if all(evt.is_set() for evt in per_variant_stops.values()):
            break
        time.sleep(0.05)
    global_stop.set()

    # Wait for fire threads to finish
    for t in fire_threads:
        t.join(timeout=1.0)

    # Determine succeeded / failed from per_variant_stops (set by workers on
    # POST 200 / 409). Fall back to /cart.json for an extra sanity check, but
    # don't override worker results — cart.json shows the anonymous session
    # cart and won't reflect member-cart adds.
    try:
        cart = _cart_json(session)
    except Exception as e:
        print(f"⚠️  最終購物車驗證查詢失敗（{e}）")
        cart = {}

    cart_qty_map: dict[int, int] = {
        item["variant_id"]: item["quantity"]
        for item in cart.get("items", [])
    }

    succeeded_set: set[Product] = set()
    for p in selected:
        # Worker set per_variant_stop for any of its variants → success
        if any(per_variant_stops[v["id"]].is_set() for v in p.variants):
            succeeded_set.add(p)
            continue
        # Otherwise fall back to cart.json (unlikely to help, but harmless)
        total = sum(cart_qty_map.get(v["id"], 0) for v in p.variants)
        if total >= p.quantity:
            succeeded_set.add(p)

    succeeded = [p for p in selected if p in succeeded_set]
    failed = [p for p in selected if p not in succeeded_set]

    print(f"\n📊 結果：{len(succeeded)}/{len(selected)} 件成功加入購物車")
    if failed:
        for p in failed:
            print(f"   ❌ {p.name}")

    get_logger().info(
        "搶購結果 %d/%d 成功；失敗=%s",
        len(succeeded), len(selected), [p.handle for p in failed],
    )
    return succeeded, failed
