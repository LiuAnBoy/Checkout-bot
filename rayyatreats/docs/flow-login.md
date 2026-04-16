# Step 1: Login Flow

## URL

```
https://www.rayyatreats.com/account/login
```

## Form Structure

```
Form ID: customer_login
Action:  POST /account/login
Class:   needs-validation
```

| Field                | Type     | Name                   | Notes            |
|----------------------|----------|------------------------|------------------|
| Email                | email    | `customer[email]`      | Visible input    |
| Password             | password | `customer[password]`   | Hidden input     |
| Remember me          | checkbox | (unnamed)              | Optional         |
| authenticity_token   | hidden   | `authenticity_token`   | CSRF, auto-filled|

## Login Request

```http
POST https://www.rayyatreats.com/account/login
Content-Type: application/x-www-form-urlencoded

customer[email]=eric141886@gmail.com
customer[password]=eric@0615
authenticity_token=<from hidden input>
```

## Success

- Redirects to: `https://www.rayyatreats.com/account/index`
- Page title: `我的帳號 rayyatreats`
- Sets `_cyberbiz_session` cookie (httpOnly, not readable via JS)

## After Login

- CSRF token available at: `<meta name="csrf-token" content="...">`
- This CSRF token is needed for all subsequent POST requests (e.g., /cart/add)

## Python Implementation Notes

```python
import requests

session = requests.Session()

# Step 1: GET login page to grab authenticity_token
resp = session.get("https://www.rayyatreats.com/account/login")
# Parse: <input name="authenticity_token" type="hidden" value="...">

# Step 2: POST login
session.post("https://www.rayyatreats.com/account/login", data={
    "customer[email]": "eric141886@gmail.com",
    "customer[password]": "eric@0615",
    "authenticity_token": token,
})

# Step 3: Verify - check redirect to /account/index
# session.cookies now contains _cyberbiz_session (auto-managed by requests)
```
