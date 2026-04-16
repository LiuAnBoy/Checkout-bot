"""rayyatreats checkout bot — main entry point."""

from dotenv import load_dotenv

load_dotenv()

from src.auth import get_session, get_csrf_token
from src.menu import select_products, print_summary
from src.poller import wait_for_products
from src.cart import add_products_to_cart
from src.checkout import do_checkout


def main() -> None:
    print("=" * 50)
    print("  rayyatreats 搶購 Bot")
    print("=" * 50 + "\n")

    # Step 1: Login
    session = get_session()

    # Step 2: Product selection menu
    print()
    selected = select_products()
    print_summary(selected)

    # Step 3: Poll for products to go live
    csrf_token = get_csrf_token(session)
    matched = wait_for_products(session, selected)

    # Step 4: Add to cart
    print("\n📥 加入購物車...")
    succeeded, failed = add_products_to_cart(session, csrf_token, matched)

    if failed:
        names = "、".join(p.name for p in failed)
        print(f"⚠️  以下商品加入失敗：{names}")

    if not succeeded:
        print("❌ 沒有商品成功加入購物車，結束")
        return

    # Step 5: Checkout via browser
    try:
        do_checkout()
        print("\n🎉 訂單已送出！")
        print("   請前往 https://www.rayyatreats.com/account/orders")
        print("   點選「前往付款」完成 3D 驗證")
    except Exception as e:
        print(f"\n❌ 結帳失敗：{e}")
        print("   請手動前往 https://www.rayyatreats.com/cart 完成結帳")


if __name__ == "__main__":
    main()
