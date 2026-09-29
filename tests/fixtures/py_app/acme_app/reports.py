# Builds the text reports for orders.
# Reports are plain text so they can be piped anywhere.
import json

from . import models
from .models import MAX_ITEMS, Order
from .services.pricing import total_price


def _format_line(order: Order) -> str:
    return f"{order.count()} items, total {total_price(order)}"


def _shout(text: str) -> str:
    return text.upper()


def _left_a():
    return _left_b()


def _left_b():
    return _left_a()


def run_report(orders: list[Order]) -> str:
    lines = [_shout(_format_line(o)) for o in orders[:MAX_ITEMS]]
    return json.dumps(lines)


def summary(orders: list[Order]) -> str:
    return _shout("summary") if models else ""


def _unused_helper():
    return 1
