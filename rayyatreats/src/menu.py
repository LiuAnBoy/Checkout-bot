"""Interactive product selection TUI."""

import sys
import tty
import termios
from dataclasses import dataclass, field


@dataclass
class Product:
    name: str
    keywords: list[str]
    is_combo: bool
    quantity: int = 0  # 0 = not selected

    def __hash__(self) -> int:
        return hash(self.name)


PRODUCTS: list[Product] = [
    # 組合包
    Product("3入組合：超級開心果＋金萱百香＋芝麻米香", ["超級開心果", "金萱", "芝麻"], is_combo=True),
    Product("3入組合：開心榛果＋焙茶＋蓮花脆餅", ["開心榛果", "焙茶", "蓮花"], is_combo=True),
    Product("2入組合：草莓蛋糕＋花生麻糬", ["草莓", "花生麻糬"], is_combo=True),
    # 單品
    Product("超級開心果脆脆", ["超級開心果"], is_combo=False),
    Product("金萱百香脆脆", ["金萱"], is_combo=False),
    Product("焙茶脆脆", ["焙茶"], is_combo=False),
    Product("花生麻糬脆脆", ["花生麻糬"], is_combo=False),
    Product("開心榛果脆脆", ["開心榛果"], is_combo=False),
    Product("蓮花脆餅脆脆", ["蓮花"], is_combo=False),
    Product("草莓蛋糕脆脆", ["草莓"], is_combo=False),
    Product("芝麻米香脆脆", ["芝麻"], is_combo=False),
]

COMBO_COUNT = sum(1 for p in PRODUCTS if p.is_combo)


def _getch() -> str:
    """Read a single keypress."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(2)
            return "\x1b" + ch2
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render(cursor: int) -> None:
    """Render the full menu."""
    # Move cursor to top of menu area
    lines = 4 + len(PRODUCTS) + 3  # header + products + footer
    print(f"\x1b[{lines}A", end="")

    selected_count = sum(1 for p in PRODUCTS if p.quantity > 0)

    print("\x1b[K📦 選擇商品  ↑↓ 移動  空白鍵 選取/取消  ←→ 調整數量 (1-2)  Enter 確認\n\x1b[K")
    print("\x1b[K  組合包：")
    for i, p in enumerate(PRODUCTS):
        if i == COMBO_COUNT:
            print("\x1b[K\n\x1b[K  單品：")
        prefix = ">" if i == cursor else " "
        if p.quantity > 0:
            box = "✔"
            qty = f" {p.quantity}"
        else:
            box = " "
            qty = "  "
        print(f"\x1b[K  {prefix} [{box}]{qty} {p.name}")
    print(f"\x1b[K\n\x1b[K  已選 {selected_count} 項 | Enter 確認")


def _initial_render() -> None:
    """Print menu for the first time."""
    selected_count = sum(1 for p in PRODUCTS if p.quantity > 0)
    print("📦 選擇商品  ↑↓ 移動  空白鍵 選取/取消  ←→ 調整數量 (1-2)  Enter 確認\n")
    print("  組合包：")
    for i, p in enumerate(PRODUCTS):
        if i == COMBO_COUNT:
            print("\n  單品：")
        if p.quantity > 0:
            box, qty = "✔", f" {p.quantity}"
        else:
            box, qty = " ", "  "
        print(f"  > [{box}]{qty} {p.name}" if i == 0 else f"    [{box}]{qty} {p.name}")
    print(f"\n  已選 {selected_count} 項 | Enter 確認")


def select_products() -> list[Product]:
    """Run the interactive menu and return selected products with quantities."""
    cursor = 0
    # Reset all quantities
    for p in PRODUCTS:
        p.quantity = 0

    _initial_render()

    while True:
        key = _getch()

        if key == "\x1b[A":  # Up
            cursor = (cursor - 1) % len(PRODUCTS)
        elif key == "\x1b[B":  # Down
            cursor = (cursor + 1) % len(PRODUCTS)
        elif key == " ":  # Space — toggle
            p = PRODUCTS[cursor]
            if p.quantity > 0:
                p.quantity = 0
            else:
                p.quantity = 1
        elif key == "\x1b[C":  # Right — increase qty
            p = PRODUCTS[cursor]
            if p.quantity > 0:
                p.quantity = min(2, p.quantity + 1)
        elif key == "\x1b[D":  # Left — decrease qty
            p = PRODUCTS[cursor]
            if p.quantity > 0:
                p.quantity = max(1, p.quantity - 1)
        elif key in ("\r", "\n"):  # Enter
            selected = [p for p in PRODUCTS if p.quantity > 0]
            if not selected:
                continue  # Must select at least one
            break
        elif key == "\x03":  # Ctrl+C
            print("\n\n取消")
            sys.exit(0)

        _render(cursor)

    print()
    return selected


def print_summary(selected: list[Product]) -> None:
    """Print final order summary."""
    print("\n📋 確認選購清單：\n")
    total = 0
    for p in selected:
        prices = {"3入組合": 1470, "2入組合": 980}
        price = next((v for k, v in prices.items() if k in p.name), 490)
        subtotal = price * p.quantity
        total += subtotal
        print(f"  {'組合' if p.is_combo else '單品'} | {p.name} × {p.quantity}  NT${subtotal}")
    print(f"\n  合計 NT${total}（不含運費）")
    print("\n按 Enter 開始等待開賣，Ctrl+C 取消")
    input()
