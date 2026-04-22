"""rayyatreats checkout bot — main entry point."""

import re
import subprocess
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import os

_REQUIRED_ENV = [
    "RAYYA_EMAIL",
    "RAYYA_PASSWORD",
    "CC_HOLDER",
    "CC_NUMBER",
    "CC_EXPIRY",
    "CC_CVV",
]

_missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
if _missing:
    print("❌ 缺少以下環境變數，請檢查 .env：")
    for k in _missing:
        print(f"   - {k}")
    raise SystemExit(1)

from src.auth import get_session, get_csrf_token
from src.menu import select_products, print_summary, Product
from src.sync import sync
from src.waiter import wait_and_fire
from src.checkout import do_checkout


def _parse_sale_time(products: list[Product]) -> datetime | None:
    """Try to parse sale time from product display_names (e.g. '4/23 中午12:30開單')."""
    for p in products:
        m = re.search(
            r"(\d{1,2})/(\d{1,2})\s*(?:中午|下午|早上)?(\d{1,2}):(\d{2})開單",
            p.display_name,
        )
        if m:
            month, day, hour, minute = (
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
            )
            return datetime(datetime.now().year, month, day, hour, minute, 0)
    return None


def _ask_sale_time() -> datetime:
    """Prompt user for sale time if it can't be parsed automatically."""
    while True:
        raw = input("⏰ 請輸入開賣時間（格式：MM/DD HH:MM，例如 04/23 12:30）：").strip()
        try:
            return datetime.strptime(f"{datetime.now().year}/{raw}", "%Y/%m/%d %H:%M")
        except ValueError:
            print("   格式不正確，請重試")


def main() -> None:
    print("=" * 50)
    print("  rayyatreats 搶購 Bot")
    print("=" * 50 + "\n")

    # R10: Clear any stale browser session before starting
    subprocess.run(
        ["agent-browser", "--session", "rayya", "close"],
        capture_output=True,
    )

    # Step 1: Login
    session = get_session()

    # Step 2: Sync products from website
    print()
    current_products = sync(session, interactive=True)

    # Step 3: Product selection menu
    print()
    selected = select_products()
    print_summary(selected)

    # Step 4: Confirm sale time
    sale_time = _parse_sale_time(current_products)
    if sale_time:
        print(f"\n🕐 偵測到開賣時間：{sale_time.strftime('%Y-%m-%d %H:%M:%S')}")
        ans = input("   確認？[Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            sale_time = _ask_sale_time()
    else:
        sale_time = _ask_sale_time()

    # Step 5: Get CSRF token and fire
    csrf_token = get_csrf_token(session)
    succeeded, failed = wait_and_fire(session, csrf_token, selected, sale_time)

    if failed:
        names = "、".join(p.name for p in failed)
        print(f"⚠️  以下商品加入失敗：{names}")

    if not succeeded:
        print("❌ 沒有商品成功加入購物車，結束")
        return

    # Step 6: Checkout via browser
    try:
        do_checkout()
        print("\n🎉 訂單已送出，等待 3DS 驗證")
        print("   請前往 https://www.rayyatreats.com/account/orders")
        print("   點選「前往付款」完成 3D 驗證")
    except Exception as e:
        print(f"\n❌ 結帳失敗：{e}")
        print("   請手動前往 https://www.rayyatreats.com/cart 完成結帳")


if __name__ == "__main__":
    main()
