"""rayyatreats checkout bot — main entry point."""

import time
from datetime import datetime, timedelta
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
from src.menu import select_products, print_summary
from src.sync import refresh as refresh_products
from src.waiter import fire
from src.checkout import do_checkout


def _next_sale_time() -> datetime:
    """Return this week's Thursday 12:30 Asia/Taipei (may be in the past)."""
    now = datetime.now(TZ)
    days_until_thursday = (3 - now.weekday()) % 7  # 0..6, keeps current week
    return now.replace(hour=12, minute=30, second=0, microsecond=0) + timedelta(days=days_until_thursday)


def main() -> None:
    print("=" * 50)
    print("  rayyatreats 搶購 Bot")
    print("=" * 50 + "\n")

    sale_time = _next_sale_time()
    print(f"🗓  開賣時間：{sale_time.strftime('%Y-%m-%d %H:%M')}（週四 12:30）")

    # Step 1: Login
    session = get_session()

    # Step 2: Warmup — keep-alive pings + refresh product cache + prefetch CSRF
    print("\n⏳ 預熱連線中...")
    try:
        session.get("https://www.rayyatreats.com", timeout=10)
        session.get("https://www.rayyatreats.com/cart.json", timeout=5)
        print("✅ 連線預熱完成")
    except Exception:
        print("⚠️  預熱失敗，繼續...")

    print("\n🔄 同步商品資料...")
    refresh_products(session)

    csrf_token = get_csrf_token(session)

    # Step 3: Product selection — user picks items before countdown
    selected = select_products()
    print_summary(selected)

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

    # Step 5: Fire immediately at sale time
    succeeded, failed = fire(session, csrf_token, selected)

    if failed:
        names = "、".join(p.name for p in failed)
        print(f"⚠️  以下商品加入失敗：{names}")

    if not succeeded:
        print("❌ 沒有商品成功加入購物車，結束")
        return

    # Step 6: Checkout via browser
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
