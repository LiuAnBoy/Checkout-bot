"""rayyatreats checkout bot — main entry point."""

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")

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
from src.sync import fetch_only, save_local
from src.waiter import fire
from src.checkout import do_checkout


def _parse_sale_time(products: list[Product]) -> datetime | None:
    """Try to parse sale time from product display_names (e.g. '4/23 中午12:30開單')."""
    now = datetime.now(TZ)
    for p in products:
        m = re.search(
            r"(\d{1,2})/(\d{1,2})\s*(早上|中午|下午)?(\d{1,2}):(\d{2})開單",
            p.display_name,
        )
        if m:
            month, day, meridiem, hour, minute = (
                int(m.group(1)),
                int(m.group(2)),
                m.group(3),
                int(m.group(4)),
                int(m.group(5)),
            )
            if meridiem == "下午" and hour < 12:
                hour += 12
            elif meridiem == "早上" and hour == 12:
                hour = 0
            sale_time = datetime(now.year, month, day, hour, minute, 0, tzinfo=TZ)
            if (sale_time - now).total_seconds() < -86400:
                sale_time = sale_time.replace(year=now.year + 1)
            return sale_time
    return None


def _ask_sale_time() -> datetime:
    """Prompt user for sale time if it can't be parsed automatically."""
    while True:
        raw = input("⏰ 請輸入開賣時間（格式：MM/DD HH:MM，例如 04/23 12:30）：").strip()
        try:
            dt = datetime.strptime(f"{datetime.now(TZ).year}/{raw}", "%Y/%m/%d %H:%M")
            dt = dt.replace(tzinfo=TZ)
            if dt <= datetime.now(TZ):
                print("   時間已過，請輸入未來的時間")
                continue
            return dt
        except ValueError:
            print("   格式不正確，請重試")


def main() -> None:
    print("=" * 50)
    print("  rayyatreats 搶購 Bot")
    print("=" * 50 + "\n")

    # Step 1: Login
    session = get_session()

    # Step 2: Ask sale time
    print()
    sale_time = _ask_sale_time()

    # Step 3: Warmup — keep-alive pings + prefetch CSRF token
    print("\n⏳ 預熱連線中...")
    try:
        session.get("https://www.rayyatreats.com", timeout=10)
        session.get("https://www.rayyatreats.com/cart.json", timeout=5)
        print("✅ 連線預熱完成")
    except Exception:
        print("⚠️  預熱失敗，繼續等待...")

    csrf_token = get_csrf_token(session)

    # Step 4: Countdown to sale_time
    while True:
        now = datetime.now(TZ)
        delta = (sale_time - now).total_seconds()
        if delta <= 0:
            break
        m, s = divmod(int(delta), 60)
        print(f"\r⏰ 距開賣 {m:02d}:{s:02d}  ", end="", flush=True)
        time.sleep(0.5)
    print()

    # Step 5: Fetch products at sale time
    sale_ts = time.time()
    print("🔍 抓取商品中...")
    try:
        products = fetch_only(session)
    except Exception as e:
        print(f"❌ 商品抓取失敗：{e}")
        return

    if not products:
        print("❌ 沒有商品可購買，結束")
        return

    save_local(products)

    # Step 6: Show elapsed + product selection menu
    elapsed = time.time() - sale_ts
    print(f"⏱  距開賣 +{elapsed:.1f}s，共 {len(products)} 項商品\n")
    selected = select_products()
    print_summary(selected)

    # Step 7: Fire
    succeeded, failed = fire(session, csrf_token, selected)

    if failed:
        names = "、".join(p.name for p in failed)
        print(f"⚠️  以下商品加入失敗：{names}")

    if not succeeded:
        print("❌ 沒有商品成功加入購物車，結束")
        return

    # Step 8: Checkout via browser
    try:
        ok = do_checkout(session)
    except Exception as e:
        print(f"\n❌ 結帳失敗：{e}")
        print("   請手動前往 https://www.rayyatreats.com/cart 完成結帳")
        return

    if ok:
        print("\n🎉 訂單已送出，等待 3DS 驗證")
        print("   請前往 https://www.rayyatreats.com/account/orders")
        print("   點選「前往付款」完成 3D 驗證")
    else:
        print("\n❌ 結帳未完成，請手動前往 https://www.rayyatreats.com/cart 完成結帳")


if __name__ == "__main__":
    main()
