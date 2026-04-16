# Step 3: Fetch Variant IDs from Product Pages

## How It Works

Each product page embeds a JSON block in an inline `<script>` tag:

```javascript
{"id":66951680,"handle":"pistachioooochocolatebar-20260415114521","title":"...","price":1470.0,
 "url":"/products/...","available":true,"options":[],
 "variants":[{"id":81350324,"product_id":66951680,"option1":null,...,"price":1470.0,...}]
}
```

## Python Extraction

```python
import re, json

resp = session.get(product_url)
# Find the JSON block containing "variants"
match = re.search(
    r'\{"id":\d+,"handle":"[^"]+","title":"[^"]*","price":[^,]+,'
    r'"url":"[^"]*","available":\w+,"options":\[[^\]]*\],'
    r'"variants":\[(.+?)\]',
    resp.text
)
if match:
    variants = json.loads('[' + match.group(1) + ']')
    # Each variant: { "id": 81350324, "product_id": 66951680, "price": 1470.0, ... }
```

### Alternative: simpler regex (variant ID only)

```python
# For single-variant products, this is enough:
match = re.search(r'"variants":\[\{"id":(\d+)', resp.text)
variant_id = int(match.group(1))
```

## Variant Data (Snapshot 2026-04-16)

### Single-variant products

| # | Name | Variant ID | Product ID | Price | Href |
|---|------|------------|------------|-------|------|
| 1 | 3入組合：超級開心果＋金萱百香＋芝麻米香脆脆 | 81350324 | 66951680 | 1470 | `/products/pistachioooochocolatebar-20260415114521` |
| 2 | 3入組合：開心榛果脆脆＋焙茶脆脆＋蓮花脆餅脆脆 | 81276652 | 66908652 | 1470 | `/products/pistachioooochocolatebar-20260410113407` |
| 3 | 2入組合：草莓蛋糕脆脆＋花生麻糬脆脆 | 81350072 | 66951427 | 980 | `/products/starwberrycakechoco-20260415114413` |
| 4 | 超級開心果脆脆 | 62230134 | 52196905 | 490 | `/products/pistachioooochocolatebar` |
| 5 | 金萱百香脆脆 | 73685259 | 60808717 | 490 | `/products/pistachioooochocolatebar-20251017132457` |
| 6 | 開心榛果脆脆 | 56464625 | 47743271 | 490 | `/products/pistachiochocolatebar` |
| 7 | 花生麻糬脆脆 | 67273447 | 55901004 | 490 | `/products/peanutmochichocobar` |
| 8 | 草莓蛋糕脆脆（冷凍保存） | 65676764 | 54808054 | 490 | `/products/starwberrycakechoco` |
| 9 | 焙茶脆脆 | 68157973 | 56504497 | 490 | `/products/hojichachocolatebar-20250624181805` |
| 10 | 芝麻米香脆脆 | 81350576 | 66951903 | 490 | `/products/sesamechocolatebar-20260415114625` |
| 11 | 蓮花脆餅脆脆 | 65951769 | 54992474 | 490 | `/products/biscoffchocolatebar` |

### Multi-variant product: NG不完美脆脆賣場

Product ID: `66951906`
Href: `/products/ngchocolate-20260415114700`

| Variant Title | Variant ID | Price |
|---------------|------------|-------|
| NG超級開心果脆脆 | 81350580 | 399 |
| NG花生麻糬脆脆 | 81350581 | 399 |
| NG芝麻米香脆脆 | 81350582 | 399 |
| NG草莓蛋糕脆脆 | 81350583 | 399 |
| NG金萱百香脆脆 | 81350584 | 399 |
| NG開心榛果脆脆 | 81350585 | 399 |
| NG焙茶脆脆 | 81350586 | 399 |
| NG覆盆莓開心果脆脆 | 81350587 | 399 |
| NG蓮花餅脆脆 | 81350588 | 399 |

## Notes

- Single-variant products: `window.selectedVariant` directly gives the variant
- Multi-variant products (like NG): need to parse the full `"variants":[...]` array from HTML
- The `option1` field contains the variant name for multi-variant products (e.g., "NG超級開心果脆脆")
- For Python scraping: use `requests` + regex on raw HTML — no need for browser/JS execution
- Variant IDs and product IDs **may change** when products are re-listed each week
- `inventoryQuantity: 0` + `inventoryPolicy: "deny"` = sold out (expected outside of drop time)
