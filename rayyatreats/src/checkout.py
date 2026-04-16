"""Browser automation for checkout via agent-browser."""

import os
import subprocess
import time


def _run(args: list[str], session_name: str = "rayya") -> str:
    """Run an agent-browser command and return stdout."""
    cmd = ["agent-browser", "--session", session_name] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def _press(key: str, session_name: str = "rayya") -> None:
    _run(["press", key], session_name)


def do_checkout(session_name: str = "rayya") -> bool:
    """
    Complete checkout via browser automation.
    Returns True if order was submitted (reached 3D page).
    """
    cc_holder = os.getenv("CC_HOLDER", "CHEN LU AN")
    cc_number = os.getenv("CC_NUMBER", "")
    cc_expiry = os.getenv("CC_EXPIRY", "")  # Format: MMYY e.g. "1230"
    cc_cvv = os.getenv("CC_CVV", "")

    if not all([cc_number, cc_expiry, cc_cvv]):
        raise RuntimeError("信用卡資訊不完整，請檢查 .env 檔案 (CC_NUMBER, CC_EXPIRY, CC_CVV)")

    print("\n🛒 開啟購物車...")
    _run(["open", "https://www.rayyatreats.com/cart"], session_name)
    _run(["wait", "--load", "networkidle"], session_name)

    url = _run(["get", "url"], session_name)
    print(f"   目前頁面: {url}")

    # Handle cart_conflict (temperature selection)
    if "cart_conflict" in url:
        print("   🌡️  選擇常溫配送...")
        output = _run(["snapshot", "-i"], session_name)
        # Find and click 常溫配送
        for line in output.splitlines():
            if "常溫配送" in line and "[ref=" in line:
                ref = line.split("[ref=")[1].split("]")[0]
                _run(["click", f"@{ref}"], session_name)
                break
        # Click 進行結帳
        for line in output.splitlines():
            if "進行結帳" in line and "[ref=" in line:
                ref = line.split("[ref=")[1].split("]")[0]
                _run(["click", f"@{ref}"], session_name)
                break
        _run(["wait", "--load", "networkidle"], session_name)
        url = _run(["get", "url"], session_name)
        print(f"   結帳頁: {url}")

    # Switch to 宅配 tab
    print("   📦 切換到宅配...")
    snapshot = _run(["snapshot", "-i"], session_name)
    for line in snapshot.splitlines():
        if "宅配" in line and "tab" in line and "[ref=" in line:
            ref = line.split("[ref=")[1].split("]")[0]
            _run(["click", f"@{ref}"], session_name)
            break
    _run(["wait", "1000"], session_name)

    # Select 黑貓冷凍宅配
    snapshot = _run(["snapshot", "-i"], session_name)
    for line in snapshot.splitlines():
        if "黑貓冷凍宅配" in line and "[ref=" in line:
            ref = line.split("[ref=")[1].split("]")[0]
            _run(["click", f"@{ref}"], session_name)
            break

    # Fill card holder name
    print("   💳 填寫信用卡...")
    snapshot = _run(["snapshot", "-i"], session_name)
    card_holder_ref = None
    for line in snapshot.splitlines():
        if "卡片上的英文姓名" in line and "[ref=" in line:
            card_holder_ref = line.split("[ref=")[1].split("]")[0]
            break

    if not card_holder_ref:
        raise RuntimeError("找不到持卡人姓名欄位")

    _run(["fill", f"@{card_holder_ref}", cc_holder], session_name)
    _run(["click", f"@{card_holder_ref}"], session_name)

    # Shift+Tab x3 to enter iframe → card number field
    for _ in range(3):
        _press("Shift+Tab", session_name)

    # Type card number digit by digit
    for digit in cc_number:
        _press(digit, session_name)

    # Tab to expiry
    _press("Tab", session_name)
    for digit in cc_expiry:
        _press(digit, session_name)

    # Tab to CVV
    _press("Tab", session_name)
    for digit in cc_cvv:
        _press(digit, session_name)

    # Click 立即結帳
    print("   📤 送出結帳...")
    snapshot = _run(["snapshot", "-i"], session_name)
    for line in snapshot.splitlines():
        if "立即結帳" in line and "[ref=" in line:
            ref = line.split("[ref=")[1].split("]")[0]
            _run(["click", f"@{ref}"], session_name)
            break

    # Wait for 3D redirect
    _run(["wait", "--load", "networkidle"], session_name)
    url = _run(["get", "url"], session_name)
    print(f"   跳轉至: {url}")

    # Close browser
    _run(["close"], session_name)

    return True
