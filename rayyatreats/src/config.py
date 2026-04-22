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
