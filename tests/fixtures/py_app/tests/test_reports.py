from acme_app.models import Order
from acme_app.reports import run_report


def test_run_report():
    assert run_report([Order(["a"])])
