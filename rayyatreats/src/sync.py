"""Product sync — fetch remote products and keep data/products.json up to date."""

import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://www.rayyatreats.com"
COLLECTION_URL = f"{BASE_URL}/collections/all"
DATA_FILE = Path(__file__).parent.parent / "data" / "products.json"


# ---------------------------------------------------------------------------
# Remote fetch
# ---------------------------------------------------------------------------


def _fetch_product_links(session: requests.Session) -> list[dict[str, str]]:
    """Return list of {handle, display_name, url} from the collection page."""
    resp = session.get(COLLECTION_URL, timeout=10)
    resp.raise_for_status()

    seen: set[str] = set()
    products = []

    # Simple regex: extract all /products/<handle> hrefs and their anchor text
    for m in re.finditer(r'href="(/products/([^"?]+))"[^>]*>([^<]+)<', resp.text):
        href, handle, raw_name = m.group(1), m.group(2), m.group(3).strip()
        if not raw_name or len(raw_name) < 5:
            continue
        if "紙袋" in raw_name or handle in seen:
            continue
        seen.add(handle)
        products.append({"handle": handle, "display_name": raw_name, "url": BASE_URL + href})

    return products


def _strip_schedule(display_name: str) -> str:
    """Remove scheduling suffixes like '4/23 中午12:30開單' and 【】 brackets."""
    name = display_name.strip("【】")
    name = re.sub(r"\s*\d+/\d+\s*[^\s]*開單.*$", "", name).strip()
    return name


def _fetch_variant(session: requests.Session, url: str) -> list[dict[str, Any]]:
    """Extract variant list from a product page."""
    resp = session.get(url, timeout=10)
    resp.raise_for_status()

    # Try full variants block first
    m = re.search(
        r'"variants":\[(\{.+?\})\]',
        resp.text,
        re.DOTALL,
    )
    if m:
        try:
            variants_raw = json.loads("[" + m.group(1) + "]")
            return [
                {"id": v["id"], "title": v.get("option1")}
                for v in variants_raw
            ]
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: grab first variant id only
    m2 = re.search(r'"variants":\[\{"id":(\d+)', resp.text)
    if m2:
        return [{"id": int(m2.group(1)), "title": None}]

    return []


def _is_combo(display_name: str) -> bool:
    return "入組合" in display_name


def _infer_price(display_name: str, variants: list[dict]) -> int:
    """Best-effort price from display name keywords; fallback to 490."""
    if "3入組合" in display_name:
        return 1470
    if "2入組合" in display_name:
        return 980
    return 490


def fetch_remote_products(session: requests.Session) -> list[dict[str, Any]]:
    """Fetch all products (excluding NG) from the website.

    Args:
        session: Authenticated requests.Session.

    Returns:
        List of product dicts matching the products.json schema.
    """
    links = _fetch_product_links(session)
    products = []
    for link in links:
        handle = link["handle"]
        display_name = link["display_name"]
        name = _strip_schedule(display_name)
        combo = _is_combo(display_name)

        variants = _fetch_variant(session, link["url"])
        price = _infer_price(display_name, variants)

        products.append(
            {
                "handle": handle,
                "name": name,
                "display_name": display_name,
                "is_combo": combo,
                "price": price,
                "variants": variants,
            }
        )
    return products


# ---------------------------------------------------------------------------
# Local I/O
# ---------------------------------------------------------------------------


def load_local_products() -> list[dict[str, Any]]:
    """Load products from data/products.json.

    Returns:
        List of product dicts, or empty list if file missing.
    """
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8")).get("products", [])


def save_local(products: list[dict[str, Any]]) -> None:
    """Write products list to data/products.json.

    Args:
        products: List of product dicts.
    """
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps({"products": products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
        local: Product list from data/products.json.

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


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def sync(
    session: requests.Session,
    interactive: bool = True,
) -> list[dict[str, Any]]:
    """Fetch remote products, show diff, optionally prompt, and save.

    Args:
        session: Authenticated requests.Session.
        interactive: If True, prompt before saving when there are changes.

    Returns:
        Current product list (remote if saved, local if fallback).
    """
    local = load_local_products()

    try:
        remote = fetch_remote_products(session)
    except Exception as e:
        print(f"⚠️  無法從網站抓取商品（{e}），使用本地快取")
        return local

    delta = diff(remote, local)
    has_changes = any(delta[k] for k in ("added", "removed", "changed"))

    if not has_changes:
        print("✅ 商品清單無變動")
        save_local(remote)
        return remote

    # Print diff
    print("📋 商品清單有變動：")
    for p in delta["added"]:
        print(f"   ＋ {p['name']}")
    for p in delta["removed"]:
        print(f"   － {p['name']}")
    for p in delta["changed"]:
        old = next((x for x in local if x["handle"] == p["handle"]), {})
        old_variants = [v["id"] for v in old.get("variants", [])]
        new_variants = [v["id"] for v in p.get("variants", [])]
        if old_variants != new_variants:
            print(f"   ～ {p['name']}  variant_id 已更新：{old_variants} → {new_variants}")
        else:
            print(f"   ～ {p['name']}  （其他欄位變動）")

    if interactive:
        ans = input("\n要更新 products.json 嗎？[Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            print("略過更新，繼續使用本地快取")
            return local

    save_local(remote)
    print("✅ products.json 已更新")
    return remote


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    from .auth import get_session as _get_session

    session = _get_session()
    result = sync(session, interactive=True)
    print(f"\n共 {len(result)} 項商品")
    sys.exit(0)
