"""Login and session management for rayyatreats."""

import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SESSION_FILE = Path(__file__).parent.parent / ".session.json"
BASE_URL = "https://www.rayyatreats.com"


def _save_session(session: requests.Session) -> None:
    """Serialize cookies preserving domain/path so reload doesn't create duplicates."""
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
        }
        for c in session.cookies
    ]
    SESSION_FILE.write_text(json.dumps({"cookies": cookies}))


def _load_session() -> requests.Session | None:
    if not SESSION_FILE.exists():
        return None
    data = json.loads(SESSION_FILE.read_text())
    session = requests.Session()

    raw = data.get("cookies", [])
    # Backward compat: old format was a dict {name: value} with no domain
    if isinstance(raw, dict):
        for name, value in raw.items():
            session.cookies.set(name, value, domain="www.rayyatreats.com", path="/")
    else:
        for c in raw:
            session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain") or "www.rayyatreats.com",
                path=c.get("path") or "/",
            )

    # Drop any empty-domain cookies that may have leaked from old format
    for c in list(session.cookies):
        if not c.domain:
            session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
    return session


def _verify_session(session: requests.Session) -> bool:
    """Check if session is still valid by hitting account page."""
    resp = session.get(f"{BASE_URL}/account/index", allow_redirects=False)
    return resp.status_code == 200


def _do_login(email: str, password: str) -> requests.Session:
    session = requests.Session()

    # GET login page for authenticity_token
    resp = session.get(f"{BASE_URL}/account/login")
    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "authenticity_token"})
    if not token_input:
        raise RuntimeError("找不到 authenticity_token，頁面結構可能已改變")
    token = token_input["value"]

    # POST login
    resp = session.post(
        f"{BASE_URL}/account/login",
        data={
            "customer[email]": email,
            "customer[password]": password,
            "authenticity_token": token,
        },
        allow_redirects=True,
    )

    if "/account/index" not in resp.url:
        raise RuntimeError("登入失敗，請確認帳號密碼是否正確")

    return session


def get_session() -> requests.Session:
    """Return an authenticated session, reusing saved cookies or logging in via .env."""
    # Try reusing saved session
    session = _load_session()
    if session and _verify_session(session):
        print("✅ 已使用儲存的登入狀態")
        return session

    # Read credentials from .env
    email = os.getenv("RAYYA_EMAIL")
    password = os.getenv("RAYYA_PASSWORD")
    if not email or not password:
        raise RuntimeError("找不到帳號密碼，請在 .env 設定 RAYYA_EMAIL 和 RAYYA_PASSWORD")

    print("🔐 登入中...", end="", flush=True)
    session = _do_login(email, password)
    _save_session(session)
    print("\r✅ 登入成功，session 已儲存")
    return session


def get_csrf_token(session: requests.Session) -> str:
    """Fetch a fresh CSRF token from the homepage."""
    resp = session.get(BASE_URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", {"name": "csrf-token"})
    if not meta:
        raise RuntimeError("找不到 CSRF token")
    return meta["content"]
