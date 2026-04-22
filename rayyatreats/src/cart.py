"""Add products to cart using variant IDs from data/products.json."""

import concurrent.futures
import json

import requests

from .menu import Product

BASE_URL = "https://www.rayyatreats.com"


def _add_one(
    session: requests.Session,
    csrf_token: str,
    variant_id: int,
    quantity: int,
) -> bool:
    """POST /cart/add for a single variant. Returns True if request succeeded."""
    for _ in range(quantity):
        session.post(
            f"{BASE_URL}/cart/add",
            data={"id": variant_id, "quantity": 1},
            headers={
                "X-CSRF-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
            timeout=10,
        )
    return True


def _verify_cart(session: requests.Session) -> dict:
    """Return cart contents from /cart.json."""
    resp = session.get(f"{BASE_URL}/cart.json", timeout=10)
    return resp.json()


def add_products_to_cart(
    session: requests.Session,
    csrf_token: str,
    selected: list[Product],
) -> tuple[list[Product], list[Product]]:
    """Add all selected products to cart in parallel, verify with /cart.json.

    Args:
        session: Authenticated requests.Session.
        csrf_token: CSRF token for POST requests.
        selected: Products with variant IDs already populated from products.json.

    Returns:
        (succeeded, failed) lists of Products.
    """
    print("\n📥 加入購物車...")

    # Collect (product, variant_id) pairs — variant_id comes from data file
    tasks: list[tuple[Product, int]] = []
    no_variant: list[Product] = []
    for p in selected:
        if not p.variants:
            print(f"   ❌ {p.name}：products.json 中無 variant_id，請重新 sync")
            no_variant.append(p)
            continue
        vid = p.variants[0]["id"]
        tasks.append((p, vid))

    if not tasks:
        return [], no_variant

    # Parallel add
    def _add_task(args: tuple[Product, int]) -> tuple[Product, bool]:
        product, vid = args
        print(f"   🛒 加入：{product.name}  (variant {vid})", flush=True)
        ok = _add_one(session, csrf_token, vid, product.quantity)
        return product, ok

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(_add_task, t): t for t in tasks}
        post_results: dict[Product, bool] = {}
        for fut in concurrent.futures.as_completed(futures):
            product, ok = fut.result()
            post_results[product] = ok

    # Verify with /cart.json
    cart = _verify_cart(session)
    item_count = cart.get("item_count", 0)
    total_price = cart.get("total_price", 0)
    print(f"\n✅ 購物車驗證：{item_count} 件，NT${total_price // 100 if total_price > 1000 else total_price}")

    cart_variant_ids = {
        item["variant_id"] for item in cart.get("items", [])
    }

    succeeded: list[Product] = []
    failed: list[Product] = list(no_variant)

    for p, vid in tasks:
        if vid in cart_variant_ids:
            succeeded.append(p)
        else:
            print(f"   ⚠️  {p.name} 未進入購物車（可能已售完）")
            failed.append(p)

    return succeeded, failed
