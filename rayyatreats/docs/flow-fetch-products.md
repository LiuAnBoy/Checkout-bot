# Step 2: Fetch All Products

## URL

```
https://www.rayyatreats.com/collections/all
```

## How to Extract

All product links are `<a href="/products/...">` elements on the page.

```python
from bs4 import BeautifulSoup

resp = session.get("https://www.rayyatreats.com/collections/all")
soup = BeautifulSoup(resp.text, "html.parser")

products = []
seen = set()
for a in soup.select('a[href*="/products/"]'):
    href = a.get("href", "")
    name = a.get_text(strip=True)
    if not href or not name or len(name) < 5 or href in seen:
        continue
    if "紙袋" in name:
        continue
    seen.add(href)
    products.append({
        "name": name,
        "href": href,
        "url": "https://www.rayyatreats.com" + href,
    })
```

## Product List (Snapshot 2026-06-25)

| # | Name | Href |
|---|------|------|
| 1 | 【3入組合：超級開心果＋金萱百香＋芝麻米香脆脆】 | `/products/pistachioooochocolatebar-20260415114521` |
| 2 | 【3入組合：抹茶脆脆＋草莓蛋糕脆脆＋花生麻糬脆脆】 | `/products/starwberrycakechoco-20260609122158` |
| 3 | 【3入組合：開心榛果脆脆＋焙茶脆脆＋蓮花脆餅脆脆】 | `/products/pistachioooochocolatebar-20260410113407` |
| 4 | 【超級開心果脆脆】 | `/products/pistachioooochocolatebar` |
| 5 | 【金萱百香脆脆】 | `/products/pistachioooochocolatebar-20251017132457` |
| 6 | 【抹茶脆脆】 | `/products/pistachioooochocolatebar-20260609120844` |
| 7 | 【開心榛果脆脆】 | `/products/pistachiochocolatebar` |
| 8 | 【花生麻糬脆脆】 | `/products/peanutmochichocobar` |
| 9 | 【草莓蛋糕脆脆】（冷凍保存！） | `/products/starwberrycakechoco` |
| 10 | 【焙茶脆脆】 | `/products/hojichachocolatebar-20250624181805` |
| 11 | 【芝麻米香脆脆】 | `/products/sesamechocolatebar-20260415114625` |
| 12 | 【蓮花脆餅脆脆】 | `/products/biscoffchocolatebar` |
| — | NG不完美脆脆賣場（塑膠袋裝）<br>*filtered out — `NG` in name* | `/products/ngchocolate-20260617151731` |
| — | RB紙袋（僅限宅配加購）<br>*filtered out — `紙袋` in name* | — |

> Changes since 2026-04-16: **＋ 抹茶脆脆 & 3入組合（抹茶＋草莓蛋糕＋花生麻糬）**, **－ 2入組合（草莓蛋糕＋花生麻糬）**.

## Notes

- Product URLs contain timestamp suffixes (e.g., `-20260415114521`) that **change each week**
- **Products only appear on the collection page at exactly 12:30** — pre-fetching before the sale returns empty or stale results (confirmed 2026-04-22)
- Must fetch at `sale_time`, not before
- Filter out "RB紙袋" (paper bag, add-on only)
- Product names contain scheduling info like "4/16 中午12:30開單" — can strip for display

## Weekly Cadence & Update Window

The store runs on a fixed weekly cycle:

| When | Store state | Notes |
|------|-------------|-------|
| **Thu 12:30** | Sale opens, products go live | Grab; also the start of the baseline-update window |
| Thu afternoon → Tue | Products listed | Live fetch works; safe to refresh the baseline |
| **Wed (all day)** | **All products delisted** | `fetch_remote_products` returns empty |
| Thu 12:30 | Next sale (display_name date rolls over) | Cycle repeats |

- **The only window to update `products.base.json` is Thu (after the grab) → Tue.** Wednesday returns an empty fetch.
- Across weeks only the `display_name` date string changes (e.g. `6/25` → `7/2`); `handle` and `variant_id` are stable, so most weeks `refresh()` reports no change and the baseline needs no edit.
- Running the bot on Wednesday is safe: `refresh()`'s `if not remote` branch falls back to the baseline and never overwrites the snapshot with an empty list.

## Fetch Trigger (Updated 2026-04-23)

`sync(session, interactive=False)` is called by `bot.py` during **warmup**, before the menu and countdown.

```python
# bot.py — triggered at warmup (before menu)
sync_products(session, interactive=False)  # refresh cache; fallback to local on failure
selected = select_products()               # user picks from cached products
# ... countdown ...
fire(session, csrf_token, selected)        # fire directly at T+0, no product fetch
```

The mass-delist guard in `sync()` prevents overwriting the cache when the site is in the between-sale delist window (Wednesday after midnight until Thursday 12:30).

## Variant ID Stability (Discovered 2026-04-23)

Handles and variant_ids are **stable across weeks** — only `display_name` suffixes like `4/23 中午12:30開單` change. This means:
- The cache from the previous sale is valid for firing at `T+0`
- No fetch is needed at sale time; the bot fires immediately from the cached variant_ids

If a variant_id is rejected (HTTP 422/404), `_fire_worker` re-fetches via `/products/{handle}.json` and retries once — see `src/waiter.py` and `src/sync.py:fetch_variant_id`.

## Parallelization

`fetch_remote_products` uses `ThreadPoolExecutor(max_workers=8)` to fetch all product pages concurrently:

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(_fetch_one, links))
```

Target: 6 products × ~30ms per page = ~30–200ms total (vs. ~600ms sequential).
