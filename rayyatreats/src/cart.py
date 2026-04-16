"""Fetch variant IDs and add products to cart."""

import re
import json

import requests
from bs4 import BeautifulSoup

from .menu import Product

BASE_URL = "https://www.rayyatreats.com"


def _get_variant_id(session: requests.Session, product_url: str) -> int | None:
    """Extract variant ID from a product page."""
    resp = session.get(product_url, timeout=10)
    match = re.search(r'"variants":\[\{"id":(\d+)', resp.text)
    if match:
        return int(match.group(1))
    return None


def _add_to_cart(
    session: requests.Session,
    csrf_token: str,
    variant_id: int,
    quantity: int,
) -> bool:
    """Add a variant to cart. Returns True if cart actually received the item."""
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
    matched: dict[Product, str],
) -> tuple[list[Product], list[Product]]:
    """
    Add all matched products to cart.

    Returns:
        (succeeded, failed) lists of Products
    """
    succeeded = []
    failed = []

    for product, url in matched.items():
        print(f"   🔍 抓取 variant ID：{product.name[:20]}...", end="", flush=True)
        variant_id = _get_variant_id(session, url)
        if not variant_id:
            print(" ❌ 找不到 variant ID")
            failed.append(product)
            continue
        print(f" (ID: {variant_id})", end="", flush=True)

        _add_to_cart(session, csrf_token, variant_id, product.quantity)
        print(" 已加入購物車")
        succeeded.append(product)

    # Verify cart
    cart = _verify_cart(session)
    item_count = cart.get("item_count", 0)
    total_price = cart.get("total_price", 0)

    print(f"\n✅ 購物車驗證：{item_count} 件，NT${total_price}")

    if item_count == 0 and succeeded:
        print("⚠️  警告：商品加入失敗（可能已售完）")
        return [], succeeded  # treat all as failed

    return succeeded, failed
