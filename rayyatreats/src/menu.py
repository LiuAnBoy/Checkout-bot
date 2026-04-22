"""Interactive product selection TUI."""

import sys
import tty
import termios
from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any

DATA_FILE = Path(__file__).parent.parent / "data" / "products.json"


@dataclass
class Product:
    handle: str
    name: str
    display_name: str
    is_combo: bool
    price: int
    variants: list[dict[str, Any]]
    quantity: int = 0  # 0 = not selected

    def __hash__(self) -> int:
        return hash(self.handle)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Product):
            return NotImplemented
        return self.handle == other.handle


def load_products() -> list["Product"]:
    """Load products from data/products.json."""
    if not DATA_FILE.exists():
        raise RuntimeError(f"找不到商品資料檔：{DATA_FILE}，請先執行 sync")
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8")).get("products", [])
    return [
        Product(
            handle=p["handle"],
            name=p["name"],
            display_name=p["display_name"],
            is_combo=p["is_combo"],
            price=p["price"],
            variants=p["variants"],
        )
        for p in raw
    ]


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


def _render(products: list[Product], combo_count: int, cursor: int) -> None:
    """Re-render the full menu in-place."""
    lines = 4 + len(products) + 3
    print(f"\x1b[{lines}A", end="")

    selected_count = sum(1 for p in products if p.quantity > 0)

    print("\x1b[K📦 選擇商品  ↑↓ 移動  空白鍵 選取/取消  ←→ 調整數量 (1-2)  Enter 確認\n\x1b[K")
    print("\x1b[K  組合包：")
    for i, p in enumerate(products):
        if i == combo_count:
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


def _initial_render(products: list[Product], combo_count: int) -> None:
    """Print menu for the first time."""
    selected_count = sum(1 for p in products if p.quantity > 0)
    print("📦 選擇商品  ↑↓ 移動  空白鍵 選取/取消  ←→ 調整數量 (1-2)  Enter 確認\n")
    print("  組合包：")
    for i, p in enumerate(products):
        if i == combo_count:
            print("\n  單品：")
        if p.quantity > 0:
            box, qty = "✔", f" {p.quantity}"
        else:
            box, qty = " ", "  "
        print(f"  > [{box}]{qty} {p.name}" if i == 0 else f"    [{box}]{qty} {p.name}")
    print(f"\n  已選 {selected_count} 項 | Enter 確認")


def select_products() -> list[Product]:
    """Run the interactive menu and return selected products with quantities."""
    products = load_products()
    combo_count = sum(1 for p in products if p.is_combo)

    cursor = 0
    for p in products:
        p.quantity = 0

    _initial_render(products, combo_count)

    while True:
        key = _getch()

        if key == "\x1b[A":  # Up
            cursor = (cursor - 1) % len(products)
        elif key == "\x1b[B":  # Down
            cursor = (cursor + 1) % len(products)
        elif key == " ":  # Space — toggle
            p = products[cursor]
            if p.quantity > 0:
                p.quantity = 0
            else:
                p.quantity = 1
        elif key == "\x1b[C":  # Right — increase qty
            p = products[cursor]
            if p.quantity > 0:
                p.quantity = min(2, p.quantity + 1)
        elif key == "\x1b[D":  # Left — decrease qty
            p = products[cursor]
            if p.quantity > 0:
                p.quantity = max(1, p.quantity - 1)
        elif key in ("\r", "\n"):  # Enter
            selected = [p for p in products if p.quantity > 0]
            if not selected:
                continue
            break
        elif key == "\x03":  # Ctrl+C
            print("\n\n取消")
            sys.exit(0)

        _render(products, combo_count, cursor)

    print()
    return selected


def print_summary(selected: list[Product]) -> None:
    """Print final order summary."""
    print("\n📋 確認選購清單：\n")
    total = 0
    for p in selected:
        subtotal = p.price * p.quantity
        total += subtotal
        print(f"  {'組合' if p.is_combo else '單品'} | {p.name} × {p.quantity}  NT${subtotal}")
    print(f"\n  合計 NT${total}（不含運費）")
    print("\n按 Enter 開始等待開賣，Ctrl+C 取消")
    input()
