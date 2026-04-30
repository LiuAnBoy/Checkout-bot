# Step 4–6: Add to Cart → Checkout → Payment

## Step 4: Add to Cart API

### Endpoint

```
POST https://www.rayyatreats.com/cart/add
```

### Headers

```
Content-Type: application/x-www-form-urlencoded
X-CSRF-Token: <from meta[name="csrf-token"]>
X-Requested-With: XMLHttpRequest
Accept: application/json
Cookie: _cyberbiz_session=<auto-managed by requests.Session>
```

### Body

```
id=81350324&quantity=1
```

- `id`: variant ID (NOT product ID)
- `quantity`: 1 or 2 (max per order varies by product)

### Success Response (HTTP 200)

```json
{
  "handle": "pistachioooochocolatebar-20260415114521",
  "title": "【3入組合：超級開心果＋金萱百香＋芝麻米香脆脆】...",
  "url": "/products/pistachioooochocolatebar-20260415114521",
  "product_id": 66951680,
  "price": 1470.0,
  "quantity": 1,
  "id": "81350324_normal_",
  "variant_id": "81350324_normal_",
  "type": "normal",
  "cart_item_id": "81350324_normal_",
  "line_price": 1470.0,
  ...
}
```

### Error Response

```json
{
  "err_msg": "加入購物車有誤，請重新嘗試"
}
```

### Multiple Items

To add multiple items, send separate POST requests for each variant ID.
They all go to the same cart (tied to session cookie).

```python
for variant_id in selected_variant_ids:
    session.post("https://www.rayyatreats.com/cart/add", data={
        "id": variant_id,
        "quantity": 1,
    }, headers={
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
    })
```

### Important Discovery (Updated 2026-04-30)

#### `/cart.json` does NOT reflect the member cart

- `/cart.json` returns the **anonymous session cart** (tied to whatever `_cyberbiz_session` cookie the request currently holds)
- The **member cart** lives at `/carts/{cart_token}` (reach via `GET /cart` → 302)
- Even when logged in, the server rotates `_cyberbiz_session` on most responses, so `/cart.json` reads from a freshly-rotated empty session and never shows items added via `POST /cart/add`
- **Do not use `/cart.json` to verify a member-cart add — it will always look empty**

#### Authoritative success signal: the POST response itself

| HTTP | Meaning |
|------|---------|
| 200 | Item added (response body echoes the line item) |
| 409 `err_msg: 購物車內商品數已超過此商品限購數量` | Already at the per-product limit — items are already in the cart, treat as success |
| 404 / 422 | Variant ID rejected — re-fetch via `/products/{handle}.json` and retry |
| 429 | Rate limited — exponential backoff |
| 5xx / other | Transient error — retry |

`_fire_worker` (in `src/waiter.py`) sets the per-variant `success_event` immediately on 200 / 409 and stops retrying that variant. The verify loop that previously polled `/cart.json` has been removed.

#### Sold-out behavior (legacy note, 2026-04-16)

- Product page shows `button "已售完" [disabled]` — UI prevents clicking
- `POST /cart/add` may still return HTTP 200; whether the item actually persists depends on backend stock state
- Final guard is the **checkout submit**: if stock ran out between add and checkout, "立即結帳" returns an error
- Because `/cart.json` is unreliable here, sold-out detection is best done at checkout time, not at cart-add time

---

## Step 5: Checkout Page

### Navigation

After adding items to cart:

```
GET /cart → 302 redirect → /carts/{cart_id}
```

Example: `/carts/4c7d79001b96013f35b2266ffb77bbd2`

The cart ID is generated per-session. Just navigate to `/cart` and it auto-redirects.

### Cart Conflict Page (Temperature Zone Selection)

When the cart contains items that support multiple shipping temperatures, navigating to `/cart` may redirect to:

```
/carts/{cart_id}/cart_conflict
```

This page requires the user to choose a temperature zone before proceeding:

| Button | Shipping Type |
|--------|--------------|
| 常溫配送 | Room temperature (default selected) |
| 冷藏配送 | Refrigerated |
| 冷凍配送 | Frozen |

After selecting, click "進行結帳" to proceed to the actual checkout page.

**Note:** If the cart only has items from one temperature zone, this page may be skipped and go directly to checkout.

### Page Structure

The checkout is a SINGLE PAGE with all fields. No multi-step wizard.

Form ID: `#main-content`
Form action: `https://www.rayyatreats.com/carts/{cart_id}`

### Pre-filled Fields (from member account, verified 2026-04-16)

The following fields are AUTO-FILLED if user is logged in:

| Field | Value (from account) | Type |
|-------|---------------------|------|
| `order[email]` | eric141886@gmail.com | hidden |
| `order[billing_address_attributes][name]` | 陳律安 | text |
| `order[billing_address_attributes][phone]` | 0916732971 | tel |
| `order[shipping_address_attributes][name]` | 陳律安 | text |
| `order[shipping_address_attributes][phone]` | 0916732971 | tel |
| `order[shipping_address_attributes][city]` | 新北市 | select (combobox) |
| `order[shipping_address_attributes][district]` | 永和區 | select (combobox) |
| `order[shipping_address_attributes][zip]` | 234 | text |
| `order[shipping_address_attributes][address1]` | 秀朗路一段45號3樓 | text |

All fields are pre-filled — **no need to fill anything except credit card holder name**.

### Shipping Options

Two tabs: 超商 (CVS pickup) / 宅配 (Home delivery)

#### Tab 1: 超商 (CVS Pickup)

Default selected. Requires choosing a store via popup.

| Hidden Field | Value |
|-------------|-------|
| `shippable[type]` | `Payment` |
| `shippable[id]` | `253086` |
| `order[shipping_rate]` | `ezcat_cvs_prepaid` |
| `order[shipping_address_attributes][seven_store_id]` | (need to select) |
| `order[shipping_address_attributes][store_name]` | (need to select) |

Available option:
- 7-11 取貨(先付款) NT$150

#### Tab 2: 宅配 (Home Delivery)

| Hidden Field | Value |
|-------------|-------|
| `shippable[type]` | `PriceBasedShippingRate` |
| `shippable[id]` | `38822` |
| `order[shipping_rate]` | `38822` |

Available options:
- 黑貓常溫宅配 NT$120
- 黑貓冷藏宅配 NT$200
- 黑貓冷凍宅配 NT$200

Address fields: county/district dropdown + zip + address (auto-filled from account)

### Payment Options

| Method | Hidden Values |
|--------|--------------|
| 信用卡 (VISA/MC/JCB) | `order[payment_id]`: `257416`, service: `cyberbizpay_gateway` |
| 銀聯卡 (UnionPay) | `order[payment_id]`: `257425` |

### Other Fields

| Field | Value |
|-------|-------|
| `order[note]` | textarea, optional |
| `order[einvoice_attributes][invoice_type]` | `default` |
| Terms checkbox | `allow-customer-terms-check-box` (auto-checked) |
| Shipping terms checkbox | `allow-shipping-terms-check-box` (auto-checked) |

### Checkout Button

"立即結帳" button submits the form.

---

## Step 6: Payment — Credit Card & 3D Secure

> Tested: 2026-04-16 (Order #63144, RB紙袋 NT$5 + 運費 NT$120 = NT$125)

### Credit Card Form Structure

The credit card form uses a **cross-origin iframe** from CYBERBIZ PAYMENTS.

```
Main page (rayyatreats.com)
├── credit_card[card_holder_name]   ← on main page, normal input
├── credit_card[save_my_card]       ← on main page, checkbox
├── credit_card[payment_token]      ← on main page, hidden (populated by iframe JS)
└── <iframe id="cyberbizpay-main-iframe" src="https://cyberbizpay.com/card_iframe?...">
    ├── Card number input       ← inside iframe
    ├── Expiry (MM/YY) input    ← inside iframe
    └── CVV/CVC input           ← inside iframe
```

### Browser Automation: Filling Credit Card via iframe

The iframe is cross-origin. Playwright's `frame_locator` accesses it via CDP,
bypassing same-origin restrictions.

#### Current approach: Playwright `frame_locator` + `type(delay=120)`

```python
iframe = page.frame_locator("iframe#cyberbizpay-main-iframe")
iframe.locator("#card-number").click()
iframe.locator("#card-number").type(cc_number, delay=120)
iframe.locator("#expire-date").click()
iframe.locator("#expire-date").type(cc_expiry, delay=120)  # MMYY e.g. "1230"
iframe.locator("#cvc").click()
iframe.locator("#cvc").type(cc_cvv, delay=120)
iframe.locator("#cvc").press("Tab")  # blur to commit
```

Selector IDs (inside iframe):
- `#card-number` — card number input
- `#expire-date` — MM/YY input
- `#cvc` — 3-digit CVV

The main-page card holder input remains a normal `<input>`:
- `input[name="credit_card[card_holder_name]"]`

The save-card checkbox:
- `#save-my-card` — saves card to account for next purchase

See `src/checkout.py` and selector constants in `src/config.py`.

#### Why `type(delay=120)` instead of `fill()` (verified 2026-04-30)

`fill()` sets the value via JS without firing per-character `input` /
`keydown` events. The cyberbizpay iframe relies on those events for two
things:

1. **Re-formatting the card number** — every 4 digits it inserts a space and
   moves the caret. With `fill()`, no events fire and the value stays
   un-formatted; the iframe's internal "card data ready" flag never flips.
2. **Tokenization on submit** — when `#checkout-button` is clicked, the
   parent page asks the iframe for a payment token via `postMessage`. If
   the iframe is not "ready", it silently returns nothing. The submit
   click then no-ops (no network request, no error message), leaving the
   user stuck on the cart page.

`type()` simulates real keystrokes, so each character fires `keydown` /
`input`. But there's a second trap: at `delay=20ms`, the iframe's space
insertion races with the next keypress and **drops characters**. Symptom:
card-number value ends up at length 11 instead of 19 (16 digits + 3
spaces). Bumping to `delay=120ms` gives the iframe time to re-format
between keystrokes.

When debugging this class of issue:
- Read `input[name="credit_card[payment_token]"]` after submit — empty
  string means tokenization never fired, which means the iframe wasn't
  "ready", which usually means the card number wasn't typed correctly.
- Check `iframe.locator("#card-number").input_value()` length: should be
  19 for a 16-digit card.

#### Legacy: agent-browser 28-press workaround (removed)

Before the Playwright migration, the bot used `agent-browser` to fill the
iframe via 28 individual `press` commands (Shift+Tab into the iframe, then
digit-by-digit). This took 5–6 seconds. With `frame_locator().type()` the
same work completes in roughly 2 seconds (16 × 120ms + a bit).

Constraints that forced the old approach:
- `agent-browser fill` / `type` do NOT work on cross-origin iframe fields
- `agent-browser snapshot` cannot see inside cross-origin iframes

These limits no longer apply — Playwright solves both.

### 3D Secure Verification Flow

After clicking "立即結帳":

```
rayyatreats.com/carts/{id}
  → POST form submit
  → redirect to nmpi.ctbcbank.com/index.jsp (中國信託 3D gateway)
    └── <iframe id="challengeMethodIframe">
        └── Bank-specific OTP page (e.g., 星展銀行 DBS ID Check)
```

#### 3D Page Content

```
交易驗證碼確認
特約商店：順立智慧股份有限公司
交易金額：125.00 TWD
信用卡號：************1468
交易日期：2026/04/16 16:36:41

[取得OTP服務密碼(Get the password)]  ← sends SMS OTP
[取消(cancel)]                       ← cancels verification
```

#### 3D Page Automation Limitation

The 3D verification page is inside **nested cross-origin iframes**:
- `nmpi.ctbcbank.com` → `challengeMethodIframe` → bank OTP page
- Playwright `frame_locator` can reach the outer `challengeMethodIframe`, but
  the inner bank OTP page is issuer-controlled and varies by card; SMS OTP
  entry is not automated.
- **Bot does not automate 3D verification.** It detects any redirect away from
  `rayyatreats.com` as the success signal (order created), then closes the
  browser. The user completes 3D-Secure manually via
  `/account/orders` → 「前往付款」.

### Key Discovery: Order Lifecycle

**The order is created the moment "立即結帳" is clicked — before payment completes.**

A confirmation email is sent immediately upon order creation (not upon payment).

| Event | Order Status | Payment Status | Email |
|-------|-------------|----------------|-------|
| Click "立即結帳" | 訂單成立 | 等待付款 | ✅ Sent immediately |
| Close/cancel 3D page | 訂單成立 | **等待付款** | (already sent) |
| Complete 3D OTP | 訂單成立 | 已付款 | Payment confirmation |

After 3D cancellation/closure:
- Order appears in `/account/orders` with status **等待付款**
- **「前往付款」** button available → retry payment anytime
- **「取消訂單」** link available → cancel order
- **「訂單明細」** button → view full order details
- Order progress: 訂單成立 → 準備出貨 → 已出貨 → 已收貨

### Test Result (Order #63144)

```
訂單編號: #63144
訂購日期: 2026-04-16 16:36
付款狀態: 等待付款 → 已取消 (manually cancelled after test)
配送狀態: 未出貨
商品: RB紙袋（僅限宅配加購，店取可於前台購買）× 1 = NT$5
運費: NT$120 (黑貓常溫宅配)
總金額: NT$125
```

---

## Bot Strategy (Updated 2026-04-23)

### Pre-sale Phase (~12:20 startup)

```
1. Login → get session cookie
2. Warmup: GET homepage + /cart.json to keep TCP alive
3. sync(session) — refresh products.json cache (fallback to local if products delisted)
4. Prefetch CSRF token
5. Show interactive menu — user selects products → Enter
6. Countdown to sale_time
```

### At sale_time (T+0)

```
7. fire(session, csrf_token, selected) — immediate POST /cart/add from cache (no fetch)
   └── on 422/404: re-fetch variant_id via /products/{handle}.json → retry once
```

No product fetch at sale time — `fire()` uses pre-synced cached variant IDs directly.

### Checkout Phase (~T+3–11s)

```
9. Navigate to /cart → handle cart_conflict → reach checkout
10. Select shipping (宅配 > 冷凍)
11. Fill credit card (Playwright frame_locator)
12. Click "立即結帳"
```

**→ Order is created. Items are reserved. Bot's job is DONE.**

### Manual Phase (user, not time-critical)

```
7. User goes to /account/orders
8. Click "前往付款" on the order
9. Complete 3D OTP verification manually
```

### Why This Works

- Steps 1–6 are the **time-critical window** (items sell out in seconds)
- Once "立即結帳" is clicked, the order exists even without payment
- User can pay later via "前往付款" — no rush
- 3D verification cannot be automated (nested cross-origin iframes)
- This is the optimal split between automation and manual action

### Cart Cleanup APIs

#### Clear entire cart

```
POST /cart/clear
X-CSRF-Token: <token>
X-Requested-With: XMLHttpRequest
```

Returns HTTP 200. Verified working.

#### Remove single item

Button class: `.delete-button` on each cart item (browser only).

### Cart Verification API

```
GET /cart.json
Accept: application/json
```

Returns:
```json
{
  "items": [...],
  "item_count": 1,
  "total_price": 5,
  "total_quantity": 1
}
```

⚠️ **`/cart.json` reflects the anonymous session cart, not the member cart.** Items added via `POST /cart/add` while logged in usually do **not** appear here. Use the POST response status (200 / 409) as the success signal instead. See the *Important Discovery* section above.

### Cart URL Structure

- `/cart` → 302 redirect → `/carts/{cart_id}` always (regardless of whether
  items exist; an empty cart still gets a hash and the page renders
  `<form id="cart_form" class="cart_empty">` with "購物車是空的")
- After `POST /cart/clear`, a fresh `/cart` request gets a *new* hash —
  the previous hash is abandoned, not reused
- `/carts/{cart_id}/cart_conflict` → temperature zone selection (if applicable)
- Cart ID is a hex hash (e.g., `a0c578301ba3013f7a3966a978772520`)
- **Cart is bound to the hash, NOT to session/login** — verified: another browser (different identity, not logged in) opening the same `/carts/{hash}/cart_conflict` URL can see the cart items (e.g., 紙袋)
- This means the cart hash acts as the sole identifier/authentication for the cart
