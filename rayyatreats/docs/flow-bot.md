# Bot Flow (Updated 2026-04-22)

## Overview

```
~12:20  startup → login → ask sale time → warmup
12:30   sale_time → fetch_only → menu → Enter → fire → checkout
```

## Detailed Steps

| Step | Code | Description |
|------|------|-------------|
| 1 | `get_session()` | Login, obtain session cookie + CSRF token |
| 2 | `_ask_sale_time()` | User inputs sale time (e.g. `04/23 12:30`) |
| 3 | warmup GETs | GET homepage + `/cart.json` to keep TCP/TLS alive |
| 4 | countdown loop | Print `⏰ 距開賣 MM:SS` every 0.5s until sale_time |
| 5 | `fetch_only(session)` | Parallel fetch collection + all product pages → variant IDs |
| 6 | `save_local(products)` | Update `data/products.json` cache |
| 7 | `select_products()` | Interactive menu, user picks items + quantity |
| 8 | `get_csrf_token(session)` | Fetch fresh CSRF token |
| 9 | `fire(session, csrf, selected)` | Immediate POST /cart/add + verify via /cart.json |
| 10 | `do_checkout(session)` | Playwright: cart → conflict → checkout → 3DS |

## Timing Model

```
T = sale_time (12:30:00)

T+0.000  countdown ends
T+0.170  GET /collections/all done
T+0.370  6 product pages fetched in parallel (worst case)
T+0.400  menu shown
T+3–10   user selects → Enter
T+3–10+ε first /cart/add fired
```

## Key Design Decisions

- **No pre-sync**: products only appear at sale_time; pre-fetching returns last week's stale variant IDs
- **No lead-time delays**: `fire()` starts immediately on Enter — no `WARMUP_LEAD_S`, `FINAL_CHECK_LEAD_S`, or `FIRE_LEAD_S`
- **Parallel variant fetch**: `ThreadPoolExecutor(max_workers=8)` fetches all product pages concurrently
- **`OVERALL_TIMEOUT_S=30`**: fire/verify loop times out 30s after Enter

## Entry Point

```bash
cd rayyatreats
python bot.py
```

## Modules

| Module | Role |
|--------|------|
| `bot.py` | Main flow orchestration |
| `src/auth.py` | Login, CSRF token |
| `src/sync.py` | `fetch_only()`, `save_local()` |
| `src/menu.py` | Interactive product selection |
| `src/waiter.py` | `fire()` — /cart/add workers + /cart.json verify |
| `src/checkout.py` | Playwright checkout automation |
| `src/config.py` | Tunable constants |
