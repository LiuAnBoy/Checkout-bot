# AGENTS.md — checkout-bot

Bots that auto-buy limited-drop products, one directory per site. Read `README.md`, then the site's `docs/`, before changing a bot.

## Repo layout

- `README.md` — the supported sites
- `docs/<site>.md` — user-facing setup and run guide for each site
- `<site>/` — the bot itself, with its own `docs/` flow write-ups
- `todos/` — gitignored work lists

## rayyatreats

A CLI bot for the weekly drop on rayyatreats.com (limited chocolate, Thursday 12:30, sold out within seconds): log in → pick products in a menu → wait for the sale → add to cart → submit the checkout → the user completes 3-D Secure by hand.

- **Stack**: Python; `requests` + BeautifulSoup for the site's endpoints, InquirerPy for the terminal menu, Playwright for the checkout (the card form is a cross-origin iframe), python-dotenv.
- **Secrets**: `rayyatreats/.env` holds the account login and the payment card and is gitignored. Never print, copy or commit its values.
- **Layout**:

  ```
  rayyatreats/
  ├── bot.py            # entry point
  ├── start.sh          # activates venv/ and runs bot.py
  ├── src/              # auth, menu, sync (product fetch + baseline), waiter (countdown + fire), cart, checkout, poller, config, logger
  ├── data/             # product baseline (products.base.json) and cache
  ├── docs/             # flow write-ups: login, products, variants, cart + checkout, bot timeline, site analysis
  └── requirements.txt
  ```

- **Run**: `cd rayyatreats && ./start.sh`.
- Before changing timing or product sync, read `rayyatreats/docs/flow-bot.md` (end-to-end timeline) and `rayyatreats/docs/flow-fetch-products.md` (weekly cadence and the baseline update window).
