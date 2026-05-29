"""Product sync — fetch remote products into the runtime snapshot.

Two files back this module:

* ``data/products.base.json`` — the committed baseline. Hand-maintained, holds
  the confirmed permanent ("常駐") product set, and is **never** overwritten by
  the bot. It is the fallback used when a live fetch returns nothing.
* ``data/products.json`` — the runtime snapshot, regenerated every run and
  gitignored. ``menu.py`` reads this file, so it always reflects the product
  list the bot actually used for the current run.
"""

import concurrent.futures
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from .logger import err_hint, get_logger

BASE_URL = "https://www.rayyatreats.com"
COLLECTION_URL = f"{BASE_URL}/collections/all"
DATA_DIR = Path(__file__).parent.parent / "data"
BASE_FILE = DATA_DIR / "products.base.json"  # committed baseline (fallback)
LIVE_FILE = DATA_DIR / "products.json"  # runtime snapshot (gitignored)


# ---------------------------------------------------------------------------
# Remote fetch
# ---------------------------------------------------------------------------


def _fetch_product_links(session: requests.Session) -> list[dict[str, str]]:
    """Return list of {handle, display_name, url} from the collection page."""
    resp = session.get(COLLECTION_URL, timeout=10)
    resp.raise_for_status()

    seen: set[str] = set()
    products = []
    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.select('a[href*="/products/"]'):
        href = a.get("href", "")
        m = re.match(r"/products/([^/?#]+)", href)
        if not m:
            continue
        handle = m.group(1)
        raw_name = a.get_text(strip=True)
        if not raw_name or len(raw_name) < 5:
            continue
        if "紙袋" in raw_name or "NG" in raw_name or handle in seen:
            continue
        seen.add(handle)
        products.append({"handle": handle, "display_name": raw_name, "url": BASE_URL + href})

    return products


def _strip_schedule(display_name: str) -> str:
    """Remove scheduling suffixes like '（4/23 中午12:30開單...）' and 【】 brackets."""
    name = re.sub(r"[【】]", "", display_name)
    name = re.sub(r"\s*（\d+/\d+.*$", "", name, flags=re.DOTALL).strip()
    return name


def _extract_variants(payload: Any) -> list[dict[str, Any]]:
    """Pull the variants list out of a CYBERBIZ product JSON payload.

    CYBERBIZ returns the product at the top level; a Shopify-style
    ``{"product": {...}}`` wrapper is tolerated as well. Any unexpected shape
    yields an empty list rather than raising.

    Args:
        payload: Decoded JSON from ``/products/{handle}.json``.

    Returns:
        The raw ``variants`` list, or [] if absent / malformed.
    """
    if not isinstance(payload, dict):
        return []
    product = payload.get("product", payload)
    if not isinstance(product, dict):
        return []
    variants = product.get("variants")
    return variants if isinstance(variants, list) else []


def _fetch_variant(session: requests.Session, handle: str) -> list[dict[str, Any]]:
    """Extract the variant list from the product JSON API.

    CYBERBIZ serves product data at ``/products/{handle}.json`` with the product
    fields at the **top level** (not wrapped in a ``"product"`` key the way
    Shopify does). The product HTML no longer embeds a ``"variants":[...]`` block,
    so this JSON endpoint is the reliable source.

    Args:
        session: Authenticated requests.Session.
        handle: Product handle (slug).

    Returns:
        List of ``{"id", "title", "price"}`` dicts; empty list if none found.
    """
    resp = session.get(f"{BASE_URL}/products/{handle}.json", timeout=10)
    resp.raise_for_status()

    variants: list[dict[str, Any]] = []
    for v in _extract_variants(resp.json()):
        if not isinstance(v, dict) or "id" not in v:
            continue
        raw_price = v.get("price")
        try:
            price = int(float(raw_price)) if raw_price is not None else None
        except (TypeError, ValueError):
            price = None
        variants.append({"id": v["id"], "title": v.get("option1"), "price": price})

    if not variants:
        get_logger().warning(
            "[E04] variant 空 handle=%s status=%s body_len=%s body[:300]=%r",
            handle,
            resp.status_code,
            len(resp.text),
            resp.text[:300],
        )

    return variants


def _is_combo(display_name: str) -> bool:
    return "入組合" in display_name


def _infer_price(display_name: str, variants: list[dict]) -> int:
    """Price from variant JSON if available; fallback to keyword inference."""
    for v in variants:
        if v.get("price") is not None:
            return v["price"]
    if "3入組合" in display_name:
        return 1470
    if "2入組合" in display_name:
        return 980
    return 490


def fetch_remote_products(
    session: requests.Session,
    local: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all products (excluding NG) from the website.

    Args:
        session: Authenticated requests.Session.
        local: Existing local products for variant fallback on fetch failure.

    Returns:
        List of product dicts matching the products.json schema.
    """
    links = _fetch_product_links(session)
    local_map = {p["handle"]: p for p in (local or [])}

    def _fetch_one(link: dict[str, str]) -> dict[str, Any] | None:
        handle = link["handle"]
        display_name = link["display_name"]
        name = _strip_schedule(display_name)
        combo = _is_combo(display_name)

        # Use a per-call session copy to avoid shared-state races across threads.
        thread_session = requests.Session()
        thread_session.cookies.update(session.cookies)
        thread_session.headers.update(session.headers)

        try:
            variants = _fetch_variant(thread_session, handle)
        except Exception:
            print(f"⚠️  {name}：商品資料抓取失敗，略過{err_hint('E03')}")
            get_logger().exception("[E03] 抓取例外 handle=%s name=%s", handle, name)
            return None

        if not variants:
            old = local_map.get(handle, {})
            old_variants = old.get("variants", [])
            if old_variants:
                print(f"⚠️  {name}：抓不到商品資料，沿用舊的{err_hint('E04')}")
                variants = old_variants
            else:
                print(f"⚠️  {name}：抓不到商品資料，也沒有舊資料可用，略過{err_hint('E04')}")
                return None

        price = _infer_price(display_name, variants)
        return {
            "handle": handle,
            "name": name,
            "display_name": display_name,
            "is_combo": combo,
            "price": price,
            "variants": variants,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_fetch_one, links))

    return [r for r in results if r is not None]


def fetch_variant_id(session: requests.Session, handle: str) -> int | None:
    """Fetch the first variant_id for a product handle via the JSON API.

    CYBERBIZ returns the product at the top level of the JSON response (no
    ``"product"`` wrapper), so variants are read directly from the root.

    Args:
        session: Authenticated requests.Session.
        handle: Product handle (slug).

    Returns:
        First variant id, or None on failure.
    """
    try:
        resp = session.get(f"{BASE_URL}/products/{handle}.json", timeout=5)
        resp.raise_for_status()
        variants = _extract_variants(resp.json())
        if variants and isinstance(variants[0], dict):
            return variants[0].get("id")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Local I/O
# ---------------------------------------------------------------------------


def load_baseline() -> list[dict[str, Any]]:
    """Load the committed baseline product set (the fallback source of truth).

    The baseline is the bot's safety net, so a missing, unreadable, or empty
    file fails loudly rather than silently degrading the fallback to an empty
    list (which would later crash the selection menu).

    Returns:
        Non-empty list of product dicts.

    Raises:
        RuntimeError: If the baseline file is missing, unreadable, or empty.
    """
    if not BASE_FILE.exists():
        raise RuntimeError(f"找不到常駐基準檔：{BASE_FILE}")
    try:
        products = json.loads(BASE_FILE.read_text(encoding="utf-8")).get("products", [])
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"常駐基準檔讀取失敗：{BASE_FILE}（{e}）") from e
    if not products:
        raise RuntimeError(f"常駐基準檔無任何商品：{BASE_FILE}")
    return products


def save_live(products: list[dict[str, Any]]) -> None:
    """Atomically write the product list to the runtime snapshot.

    Writes to a temp file in the same directory and ``os.replace``s it into
    place so an interrupted or concurrent write can never leave a half-written
    ``data/products.json``.

    Args:
        products: List of product dicts.
    """
    LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"products": products}, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=LIVE_FILE.parent, prefix=".products.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, LIVE_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff(
    remote: list[dict[str, Any]],
    local: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compare remote vs local by handle.

    Args:
        remote: Product list fetched from website.
        local: Product list to compare against (the baseline).

    Returns:
        Dict with keys 'added', 'removed', 'changed'.
    """
    remote_map = {p["handle"]: p for p in remote}
    local_map = {p["handle"]: p for p in local}

    added = [p for h, p in remote_map.items() if h not in local_map]
    removed = [p for h, p in local_map.items() if h not in remote_map]
    changed = [
        p
        for h, p in remote_map.items()
        if h in local_map and p != local_map[h]
    ]
    return {"added": added, "removed": removed, "changed": changed}


def _print_diff(remote: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> None:
    """Print how the live list differs from the committed baseline (info only)."""
    delta = diff(remote, baseline)
    if not any(delta[k] for k in ("added", "removed", "changed")):
        print("✅ 產品清單沒有變動")
        return

    print("📋 產品清單有變動：")
    for p in delta["added"]:
        print(f"   ＋ 新增：{p['name']}")
    for p in delta["removed"]:
        print(f"   － 下架：{p['name']}")
    for p in delta["changed"]:
        old = next((x for x in baseline if x["handle"] == p["handle"]), {})
        old_v = [v["id"] for v in old.get("variants", [])]
        new_v = [v["id"] for v in p.get("variants", [])]
        if old_v != new_v:
            print(f"   ～ {p['name']}：商品編號變了（{old_v} → {new_v}）")
        else:
            print(f"   ～ {p['name']}：內容有更新")


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


def refresh(session: requests.Session) -> list[dict[str, Any]]:
    """Fetch live products into the runtime snapshot, falling back to baseline.

    The committed ``products.base.json`` is the source of truth and is never
    modified. On every run a live fetch is attempted:

    * If it yields any products, that list is written to ``products.json`` and a
      diff against the baseline is printed for visibility.
    * If the fetch raises or yields nothing, the baseline is used unchanged and
      still written to ``products.json`` so the snapshot reflects the run.

    Args:
        session: Authenticated requests.Session.

    Returns:
        The product list the run should use (live if available, else baseline).
    """
    log = get_logger()
    baseline = load_baseline()

    try:
        remote = fetch_remote_products(session, local=baseline)
    except Exception:
        print(f"⚠️  商品清單更新失敗，改用內建的備用清單{err_hint('E01')}")
        log.exception("[E01] 整體抓取失敗")
        save_live(baseline)
        return baseline

    if not remote:
        print(f"⚠️  沒抓到任何商品，改用內建的備用清單{err_hint('E02')}")
        log.warning("[E02] fallback 到備用清單（baseline %d 項）", len(baseline))
        save_live(baseline)
        return baseline

    _print_diff(remote, baseline)
    save_live(remote)
    print("✅ 產品清單已更新")
    log.info("使用即時清單 %d 項", len(remote))
    return remote


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    from .auth import get_session as _get_session

    session = _get_session()
    result = refresh(session)
    print(f"\n共 {len(result)} 項商品")
    sys.exit(0)
