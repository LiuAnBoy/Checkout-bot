"""Browser automation for checkout via Playwright."""

import os

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .config import (
    CART_CONFLICT_TEMP_ZONE,
    CHECKOUT_ERROR_SELECTORS,
    CHECKOUT_HEADLESS,
    CHECKOUT_TIMEOUT_MS,
    SEL_CARD_HOLDER_NAME,
    SEL_CART_CONFLICT_PROCEED,
    SEL_CART_CONFLICT_TEMP,
    SEL_CC_CVV,
    SEL_CC_EXPIRY,
    SEL_CC_IFRAME,
    SEL_CC_NUMBER,
    SEL_CC_SAVED_CARD,
    SEL_CHECKOUT_SUBMIT,
    SEL_SAVE_MY_CARD,
    SEL_SHIPPING_OPTION_FROZEN,
    SEL_SHIPPING_TAB_HOME_DELIVERY,
)

BASE_URL = "https://www.rayyatreats.com"


def _session_to_playwright_cookies(session: requests.Session) -> list[dict]:
    """Convert requests.Session cookies to Playwright cookie format."""
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain or "www.rayyatreats.com",
            "path": c.path or "/",
        }
        for c in session.cookies
    ]


def do_checkout(session: requests.Session) -> bool:
    """Complete checkout via Playwright browser automation.

    Navigates to /cart, handles optional cart_conflict temperature-zone
    selection, selects home delivery (黑貓冷凍宅配), fills credit card
    details, submits the order, and waits for the 3DS redirect.

    The browser closes automatically once the 3DS URL is detected (= order
    created, stock locked). The user completes 3DS manually via
    /account/orders → 前往付款.

    Args:
        session: Authenticated requests.Session whose cookies are forwarded
                 to the Playwright browser context.

    Returns:
        True if the 3DS redirect was detected (order created).
        False if checkout failed (timeout or visible error on page).

    Raises:
        RuntimeError: If credit card env vars (CC_NUMBER / CC_EXPIRY / CC_CVV)
                      are not set.
    """
    cc_holder = os.getenv("CC_HOLDER", "CHEN LU AN")
    cc_number = os.getenv("CC_NUMBER", "")
    cc_expiry = os.getenv("CC_EXPIRY", "")
    cc_cvv = os.getenv("CC_CVV", "")

    if not all([cc_number, cc_expiry, cc_cvv]):
        raise RuntimeError("信用卡資訊不完整，請檢查 .env 檔案 (CC_NUMBER, CC_EXPIRY, CC_CVV)")

    cookies = _session_to_playwright_cookies(session)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=CHECKOUT_HEADLESS)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()

        # ── 1. Navigate to cart ──────────────────────────────────────────────
        print("\n🛒 開啟購物車...")
        page.goto(f"{BASE_URL}/cart", wait_until="load")
        page.wait_for_timeout(1000)
        url = page.url
        print(f"   頁面: {url}")

        # ── 2. Handle cart_conflict (temperature zone selection) ─────────────
        if "cart_conflict" in url:
            print(f"   🌡️  選擇 {CART_CONFLICT_TEMP_ZONE}...")
            page.locator(SEL_CART_CONFLICT_TEMP).click()
            page.wait_for_timeout(300)
            print("   → 進行結帳...")
            page.locator(SEL_CART_CONFLICT_PROCEED).click()
            page.wait_for_load_state("load")
            page.wait_for_timeout(800)
            url = page.url
            print(f"   結帳頁: {url}")

        # ── 3. Select 宅配 tab ───────────────────────────────────────────────
        print("   📦 切換到宅配...")
        # JS click is more reliable than Playwright click for tab elements
        # that may need scrolling in headless mode.
        page.evaluate(
            "sel => document.querySelector(sel)?.click()",
            SEL_SHIPPING_TAB_HOME_DELIVERY,
        )
        # Wait for 黑貓冷凍配送 option to be visible before clicking
        page.locator(SEL_SHIPPING_OPTION_FROZEN).wait_for(timeout=5000)

        # ── 4. Select 黑貓冷凍宅配 ────────────────────────────────────────────
        print("   🐱 選擇黑貓冷凍宅配...")
        page.locator(SEL_SHIPPING_OPTION_FROZEN).click()

        # ── 5. Payment: reuse a saved card if one exists, else fill a new one ─
        # When the account has a stored card, the checkout renders a
        # "選擇常用信用卡" option (active by default) and no card iframe at all.
        # Waiting for the iframe in that case would time out. So: if the
        # saved-card option is present, make sure it's selected and skip the
        # whole card-entry flow.
        saved_card = page.locator(SEL_CC_SAVED_CARD)
        if saved_card.count() > 0:
            print("   💳 偵測到常用信用卡，沿用已存卡片（跳過填卡）...")
            if "active" not in (saved_card.first.get_attribute("class") or ""):
                saved_card.first.click()
                page.wait_for_timeout(300)
        else:
            print("   💳 填寫信用卡...")
            page.locator(SEL_CARD_HOLDER_NAME).fill(cc_holder)

            # Playwright frame_locator accesses cross-origin iframes via CDP,
            # bypassing the same-origin restriction that blocks agent-browser.
            # Use .type() instead of .fill() — fill() sets the value via JS but
            # may not fire the input/change events cyberbizpay iframe relies on
            # to mark card data as ready and tokenize on submit.
            iframe = page.frame_locator(SEL_CC_IFRAME)
            iframe.locator(SEL_CC_NUMBER).wait_for(timeout=8000)
            # delay must be long enough for cyberbizpay iframe to re-format the
            # value after every 4 digits (it inserts spaces, which moves the
            # caret). Anything below ~100ms causes characters to be dropped.
            iframe.locator(SEL_CC_NUMBER).click()
            iframe.locator(SEL_CC_NUMBER).type(cc_number, delay=120)
            iframe.locator(SEL_CC_EXPIRY).click()
            iframe.locator(SEL_CC_EXPIRY).type(cc_expiry, delay=120)
            iframe.locator(SEL_CC_CVV).click()
            iframe.locator(SEL_CC_CVV).type(cc_cvv, delay=120)
            # Blur the last field to commit the value and let the iframe finalize
            # its "ready" state.
            iframe.locator(SEL_CC_CVV).press("Tab")

            # 保存我的信用卡資訊（方便下次自動帶入）
            page.locator(SEL_SAVE_MY_CARD).check()

        # ── 7. Submit order ───────────────────────────────────────────────────
        print("   📤 送出結帳...")
        page.locator(SEL_CHECKOUT_SUBMIT).click()

        # ── 8. Wait for redirect away from rayyatreats = order created ──────────
        try:
            page.wait_for_url(
                lambda url: "rayyatreats.com" not in url,
                timeout=CHECKOUT_TIMEOUT_MS,
            )
            final_url = page.url
            print(f"   ✅ 訂單已成立，跳轉至: {final_url}")
            print("   → 請前往 /account/orders 完成付款驗證")
            return True
        except PlaywrightTimeoutError:
            # Checkout stayed on rayyatreats — extract error message
            error_text = "無法取得錯誤訊息"
            try:
                el = page.locator(CHECKOUT_ERROR_SELECTORS).first
                el.wait_for(timeout=2000)
                error_text = el.text_content() or error_text
                error_text = error_text.strip()
            except PlaywrightTimeoutError:
                pass
            print(f"   ❌ 結帳失敗（{CHECKOUT_TIMEOUT_MS // 1000}s timeout）：{error_text}")
            return False
