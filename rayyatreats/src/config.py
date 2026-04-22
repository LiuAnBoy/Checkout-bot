"""Tunable parameters for the checkout bot."""

# Pre-sale warmup / timing
WARMUP_LEAD_S: float = 30.0        # GET one product page T-30s before sale
FINAL_CHECK_LEAD_S: float = 5.0    # GET /cart.json T-5s before sale
FIRE_LEAD_S: float = 0.5           # Start fire workers T-0.5s before sale

# Fire loop
FIRE_INTERVAL_MS: int = 100        # ms between /cart/add attempts per worker
MAX_ATTEMPTS_PER_VARIANT: int = 5  # give up after this many attempts

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

CHECKOUT_HEADLESS: bool = _os.getenv("HEADLESS", "false").lower() == "true"
CHECKOUT_3DS_URL_PATTERN: str = "**ctbcbank.com/**"
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
