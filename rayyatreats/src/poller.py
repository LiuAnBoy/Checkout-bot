"""Poll the collection page until selected products appear."""

import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .menu import Product

COLLECTION_URL = (
    "https://www.rayyatreats.com/collections/"
    "%E8%84%86%E8%84%86%E5%B7%A7%E5%85%8B%E5%8A%9B-crunchy-chocolate-bar"
)


def _fetch_product_links(session: requests.Session) -> dict[str, str]:
    """Return {product_name: product_url} from the collection page."""
    resp = session.get(COLLECTION_URL, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}
    seen = set()
    for a in soup.select('a[href*="/products/"]'):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if not href or not name or len(name) < 5 or href in seen:
            continue
        if "紙袋" in name:
            continue
        seen.add(href)
        result[name] = "https://www.rayyatreats.com" + href
    return result


def _match(product_links: dict[str, str], selected: list[Product]) -> dict[Product, str]:
    """Match selected products to their URLs using keywords."""
    matched: dict[Product, str] = {}
    for p in selected:
        for name, url in product_links.items():
            if all(kw in name for kw in p.keywords):
                matched[p] = url
                break
    return matched


def wait_for_products(
    session: requests.Session,
    selected: list[Product],
    interval: float = 1.0,
) -> dict[Product, str]:
    """Poll until all selected products are found. Returns {Product: url}."""
    print("\n⏳ 開始輪詢，等待商品上架...")
    start = time.time()
    attempt = 0

    while True:
        attempt += 1
        now = datetime.now().strftime("%H:%M:%S")
        try:
            links = _fetch_product_links(session)
            matched = _match(links, selected)

            found = len(matched)
            total = len(selected)
            elapsed = int(time.time() - start)
            print(
                f"\r   [{now}] 第 {attempt} 次輪詢，找到 {found}/{total} 件  已等待 {elapsed}s   ",
                end="",
                flush=True,
            )

            if found == total:
                print(f"\n\n🎯 所有商品已上架！")
                return matched

        except Exception as e:
            print(f"\r   [{now}] 輪詢失敗: {e}，重試中...                    ", end="", flush=True)

        time.sleep(interval)
