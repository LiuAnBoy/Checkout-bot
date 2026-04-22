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
    VERIFY_INTERVAL_MS,
)
from .menu import Product

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
) -> int:
    """Single POST /cart/add. Returns HTTP status code."""
    resp = session.post(
        f"{BASE_URL}/cart/add",
        data={"id": variant_id, "quantity": 1},
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        },
        timeout=5,
    )
    return resp.status_code


# ---------------------------------------------------------------------------
# Fire + Verify loops
# ---------------------------------------------------------------------------


def _fire_worker(
    session: requests.Session,
    csrf_token: str,
    product: Product,
    variant_id: int,
    stop_event: threading.Event,
) -> None:
    """Per-variant fire loop: POST /cart/add at FIRE_INTERVAL_MS until done."""
    attempts = 0
    backoff_idx = 0

    while not stop_event.is_set() and attempts < MAX_ATTEMPTS_PER_VARIANT:
        try:
            status = _add_to_cart(session, csrf_token, variant_id)
        except Exception:
            _sleep_ms(FIRE_INTERVAL_MS)
            continue

        attempts += 1

        if status == 429:
            delay = BACKOFF_429_MS[min(backoff_idx, len(BACKOFF_429_MS) - 1)]
            backoff_idx += 1
            _sleep_ms(delay)
        else:
            backoff_idx = 0
            _sleep_ms(FIRE_INTERVAL_MS)

    if attempts >= MAX_ATTEMPTS_PER_VARIANT and not stop_event.is_set():
        print(f"   ⚠️  {product.name}：已達最大嘗試次數 ({MAX_ATTEMPTS_PER_VARIANT})")


def _verify_loop(
    session: requests.Session,
    expected_count: int,
    stop_event: threading.Event,
    per_variant_stops: dict[int, threading.Event],
    variant_qty: dict[int, int],
    deadline: float,
) -> int:
    """Poll /cart.json every VERIFY_INTERVAL_MS. Returns final item_count."""
    prev_count = 0

    while not stop_event.is_set() and time.monotonic() < deadline:
        try:
            cart = _cart_json(session)
        except Exception as e:
            print(f"⚠️  /cart.json 查詢失敗：{e}")
            _sleep_ms(VERIFY_INTERVAL_MS)
            continue

        count = cart.get("item_count", 0)

        if count > prev_count:
            cart_qty: dict[int, int] = {
                item["variant_id"]: item["quantity"]
                for item in cart.get("items", [])
            }
            for vid, evt in per_variant_stops.items():
                if not evt.is_set() and cart_qty.get(vid, 0) >= variant_qty[vid]:
                    evt.set()
            prev_count = count

        if count >= expected_count:
            stop_event.set()
            return count

        _sleep_ms(VERIFY_INTERVAL_MS)

    stop_event.set()
    return prev_count


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
    variant_qty: dict[int, int] = {vid: variant_map[vid].quantity for vid in variant_map}

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
            args=(session, csrf_token, product, vid, combined_stops[vid]),
            daemon=True,
        )
        t.start()
        fire_threads.append(t)

    # Launch verify loop
    deadline = time.monotonic() + OVERALL_TIMEOUT_S
    expected = sum(p.quantity for p in selected)
    _verify_loop(
        session, expected, global_stop, per_variant_stops, variant_qty, deadline
    )

    # Wait for fire threads to finish
    for t in fire_threads:
        t.join(timeout=1.0)

    # Determine succeeded / failed by checking cart
    try:
        cart = _cart_json(session)
    except Exception as e:
        print(f"⚠️  最終購物車驗證失敗（{e}），結果可能不準確")
        cart = {}

    cart_qty_map: dict[int, int] = {
        item["variant_id"]: item["quantity"]
        for item in cart.get("items", [])
    }

    succeeded_set: set[Product] = set()
    for p in selected:
        total = sum(cart_qty_map.get(v["id"], 0) for v in p.variants)
        if total >= p.quantity:
            succeeded_set.add(p)

    succeeded = [p for p in selected if p in succeeded_set]
    failed = [p for p in selected if p not in succeeded_set]

    print(f"\n📊 結果：{len(succeeded)}/{len(selected)} 件成功加入購物車")
    if failed:
        for p in failed:
            print(f"   ❌ {p.name}")

    return succeeded, failed
