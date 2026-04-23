# Bot Flow (Updated 2026-04-23)

## Overview

```
~12:00  startup → login → warmup (ping + sync cache) → menu → user selects → Enter
12:30   countdown ends → fire immediately (no fetch) → checkout
```

## Detailed Steps

| Step | Code | Description |
|------|------|-------------|
| 1 | `get_session()` | Login, obtain session cookie |
| 2 | warmup GETs | GET homepage + `/cart.json` to keep TCP/TLS alive |
| 3 | `sync(session, interactive=False)` | Fetch + diff products, update `data/products.json`; fallback to local cache on failure |
| 4 | `get_csrf_token(session)` | Prefetch CSRF token |
| 5 | `select_products()` | Interactive menu — user picks items + quantity from cached products |
| 6 | `print_summary()` + Enter | User confirms selection; Enter starts countdown |
| 7 | countdown loop | Print `⏰ 距開賣 MM:SS` every 0.5s until sale_time |
| 8 | `fire(session, csrf, selected)` | Immediate POST /cart/add + verify via /cart.json |
| 9 | `do_checkout(session)` | Playwright: cart → conflict → checkout → 3DS |

## Timing Model

```
T = sale_time (12:30:00)

T-N     user selects items and confirms → countdown starts
T+0.000 countdown ends → fire() called immediately
T+0.0xx first /cart/add fired (no product fetch needed)
```

## Key Design Decisions

- **Stable variant IDs**: handles and variant_ids are consistent week-to-week; only `display_name` suffixes change. Cache is valid for fire at T+0.
- **Pre-sync at warmup**: `sync()` refreshes the cache before the menu is shown. Mass-delist guard prevents overwriting cache during the between-sale delist window.
- **No fetch at T=0**: `fire()` uses the pre-synced cache directly — zero delay at sale time.
- **422/404 fallback in fire**: if a variant_id is rejected, `_fire_worker` re-fetches via `/products/{handle}.json` and retries once.
- **No lead-time delays**: `fire()` starts immediately at `sale_time`.

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
| `src/sync.py` | `sync()`, `fetch_variant_id()` |
| `src/menu.py` | Interactive product selection |
| `src/waiter.py` | `fire()` — /cart/add workers + /cart.json verify |
| `src/checkout.py` | Playwright checkout automation |
| `src/config.py` | Tunable constants |
