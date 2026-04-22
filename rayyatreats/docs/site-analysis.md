# Rayyatreats Site Analysis

> Analyzed: 2026-04-16
> URL: https://www.rayyatreats.com
> Platform: CYBERBIZ (cyberbiz.io)
> CDN: cdn-next.cybassets.com

## Drop Schedule

- Every **Thursday at 12:30 PM (UTC+8)**
- Ships within 5 business days (skip Sun/Mon)

## Product Availability Behaviour (Confirmed 2026-04-22)

- **Products are NOT pre-listed before the sale.** The entire collection (except RB紙袋) disappears between drops and re-appears at exactly 12:30.
- Confirmed by owner: "12:30 才會看到商品"
- Pre-fetching variant IDs before 12:30 returns stale data from the previous week. Using those IDs for `/cart/add` at 12:30 causes all requests to fail.
- **The bot must fetch product/variant data at `sale_time`, not during startup.** See `flow-fetch-products.md`.

## Product: 3-pack Combo (Pistachio + Oolong + Sesame)

| Field             | Value                                              |
|-------------------|----------------------------------------------------|
| Product URL       | `/products/pistachioooochocolatebar-20260415114521` |
| Product ID        | `66951680`                                         |
| Variant ID        | `81350324`                                         |
| Price             | NT$1,470                                           |
| Inventory Policy  | `deny` (cannot purchase when stock = 0)            |
| Per-order Limit   | 2 units                                            |

## Add to Cart API

```
POST https://www.rayyatreats.com/cart/add
Content-Type: application/x-www-form-urlencoded
X-CSRF-Token: <from meta[name="csrf-token"]>
Cookie: _cyberbiz_session=<session_value>

Body:
  id=81350324       # variant ID
  quantity=1        # 1 or 2 (max 2 per order)
```

### Response

- **Success**: JSON with cart data, HTTP header `x-request-id`
- **Failure**: `{ "err_msg": "..." }`

### Quick Buy

Same endpoint, but after adding to cart, redirect to `/cart` for checkout.
The "quick buy" button sets `data-buy="quick_buy"` which triggers `window.location = "/cart"` after success.

## Authentication

- Cookie: `_cyberbiz_session` (Rails encrypted session)
- Additional cookies: `cacheable=1`, `inferred_country=TW`
- CSRF token: `meta[name="csrf-token"]` (changes per page load)
- `authenticity_token`: hidden input in forms (same purpose as CSRF)
- Some products may require login ("login to check eligibility" button exists)

## Button State Logic

The page contains multiple hidden buttons. JavaScript toggles visibility based on product state:

| Class                | Text         | When Shown                    |
|----------------------|--------------|-------------------------------|
| `btn_not_sale`       | Not on sale  | Before drop time              |
| `addToCart`          | Add to cart  | In stock, eligible            |
| `btn-quick_buy`     | Buy now      | In stock, eligible            |
| `btn_soldout`       | Sold out     | Stock = 0                     |
| `btn_login_to_view` | Login to view| Not logged in, restricted     |
| `btn_not_eligible`  | Not eligible | Logged in but no access       |

## Frontend JS Architecture

Key scripts (CYBERBIZ platform):
- `cart-*.js` — cart operations
- `product_variant-*.js` — variant selection logic
- `product_info-*.js` — product display and button state
- `fast_events-*.js` — event handling

Key `window` globals:
- `window.selectedVariant` — current variant object `{ id, price, inventoryQuantity, inventoryPolicy, ... }`
- `window.productInfo` — product metadata `{ id, name, price, brand, category }`
- `window.ProductVariants` — all variants array
- `window.addToCart` — the add-to-cart function (jQuery AJAX `POST /cart/add`)
- `window.pullNavCart()` — refresh cart UI

## addToCart Function (Decompiled)

```javascript
// Simplified from minified source
function addToCart() {
  // 1. Show loading
  ajaxLoadingMsg("loading");

  // 2. Get variant info
  var variantId = selectedVariant.id;
  var quantity = $("#product .product_quantity input").val();

  // 3. POST to /cart/add
  $.ajax({
    method: "POST",
    url: "/cart/add",
    data: {
      id: variantId,
      quantity: quantity,
      type: $(this).data("type"),
      collection_id: $(this).data("collection_id")
    },
    dataType: "json"
  }).done(function(data, status, xhr) {
    ajaxLoadingMsg("success");
    // Update cart count in nav
    // If quick_buy -> redirect to /cart
    // Otherwise -> open cart drawer
  }).fail(function(xhr) {
    // Show error message
    window.msg(xhr.responseJSON.err_msg, "warning").show();
  });
}
```

## All Products (from collection page)

| Product                                          | Slug (partial)                  |
|--------------------------------------------------|---------------------------------|
| 3-pack: Pistachio + Oolong + Sesame              | `pistachioooochocolatebar-*`    |
| 3-pack: Hazelnut + Hojicha + Lotus Biscuit       | (different slug)                |
| 2-pack: Strawberry Cake + Peanut Mochi           | (different slug)                |
| Pistachio (single)                               | (different slug)                |
| Oolong (single)                                  | (different slug)                |
| Hazelnut (single)                                | (different slug)                |
| Peanut Mochi (single)                            | (different slug)                |
| Strawberry Cake (single, frozen)                 | (different slug)                |
| Hojicha (single)                                 | (different slug)                |
| Sesame Rice Crispy (single)                      | (different slug)                |
| Lotus Biscuit (single)                           | (different slug)                |
| NG Imperfect batch (plastic bag)                 | (different slug)                |
| Paper bag (add-on only, delivery only)           | (different slug)                |

## Notes

- Product URLs contain a timestamp suffix (e.g., `-20260415114521`) which likely changes each week's drop
- The variant ID and product ID may also change with new drops — need to re-fetch before each Thursday
- No anti-bot measures detected (no CAPTCHA, no rate limiting visible)
- The CSRF token must be fetched fresh before each add-to-cart request (it's per-session)
