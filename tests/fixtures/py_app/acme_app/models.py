"""Data shapes for orders.

A second paragraph that must not appear in the header.
"""

MAX_ITEMS = 50
default_currency = "USD"


class Order:
    """One customer order."""

    def __init__(self, items: list[str], currency: str = default_currency) -> None:
        self.items = items
        self.currency = currency

    def count(self) -> int:
        return len(self.items)

    async def refresh(self, source: "dict[str, dict[str, list[tuple[int, str]]]]") -> None:
        self.items = list(source)
