"""Tunable parameters for the checkout bot."""

# Fire loop
FIRE_INTERVAL_MS: int = 100          # ms between /cart/add attempts per worker
MAX_ATTEMPTS_PER_VARIANT: int = 100  # give up after this many attempts (~10s at 100ms)

# Verify loop
VERIFY_INTERVAL_MS: int = 200      # ms between /cart.json polls

# 429 exponential backoff delays (ms), cycling back to FIRE_INTERVAL_MS after
BACKOFF_429_MS: list[int] = [500, 1000, 2000]

# Overall timeout after T+0
OVERALL_TIMEOUT_S: float = 30.0

# ---------------------------------------------------------------------------
# Checkout (Playwright)
# ---------------------------------------------------------------------------

import os as _os

CHECKOUT_HEADLESS: bool = _os.getenv("HEADLESS", "true").lower() == "true"
CHECKOUT_TIMEOUT_MS: int = 15_000
CHECKOUT_ERROR_SELECTORS: str = ".error, .alert, .notice, [role=alert], .flash"

# cart_conflict temperature zone — matches the button text on the conflict page.
# Must align with SEL_SHIPPING_OPTION_FROZEN: choosing 冷凍配送 here makes the
# checkout page expose 黑貓冷凍宅配 as the only 宅配 option.
CART_CONFLICT_TEMP_ZONE: str = "冷凍配送"

# CSS selectors — keep centralised here so a site redesign is a one-line fix.
SEL_CART_CONFLICT_TEMP = f"button.select-label:has-text('{CART_CONFLICT_TEMP_ZONE}')"
SEL_CART_CONFLICT_PROCEED = "button#checkout-button"
SEL_SHIPPING_TAB_HOME_DELIVERY = "a#homeDelivery-shipping-tab"
SEL_SHIPPING_OPTION_FROZEN = "button#homeDelivery-shipping-button-38824"
SEL_CARD_HOLDER_NAME = 'input[name="credit_card[card_holder_name]"]'
SEL_SAVE_MY_CARD = "#save-my-card"
SEL_CHECKOUT_SUBMIT = "button#checkout-button"
SEL_CC_IFRAME = "iframe#cyberbizpay-main-iframe"
SEL_CC_NUMBER = "#card-number"
SEL_CC_EXPIRY = "#expire-date"
SEL_CC_CVV = "#cvc"

# Saved-card vs new-card sub-options under the 信用卡 payment method. When the
# account has a stored card, "選擇常用信用卡" is present and active by default and
# NO card iframe is rendered — filling must be skipped. Match on the stable
# data-translate-keys attribute rather than display text.
SEL_CC_SAVED_CARD = '.checkable-radio:has([data-translate-keys="creditcard.select_my_card"])'
SEL_CC_USE_OTHER_CARD = '.checkable-radio:has([data-translate-keys="creditcard.use-other-card"])'
