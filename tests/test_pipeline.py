from decimal import Decimal

import pytest

from watchtower.models import MonitorType
from watchtower.pipeline import extract_html, make_candidate, normalize_text, parse_price, text_difference


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1,299.99", Decimal("1299.99")),
        ("€1.299,99", Decimal("1299.99")),
        ("1.299,99 €", Decimal("1299.99")),
        ("1 299,99", Decimal("1299.99")),
        ("₺1.299,00", Decimal("1299.00")),
        ("1.299 TL", Decimal("1299")),
    ],
)
def test_price_formats(raw: str, expected: Decimal) -> None:
    assert parse_price(raw) == expected


def test_ignore_selector_and_whitespace() -> None:
    html, text, count = extract_html(
        b"<main><h1> Product </h1><time>12:31:44</time><p>$100</p></main>",
        selector="main",
        ignore_selectors=["time"],
    )
    assert "12:31" not in html
    assert normalize_text(text) == "Product\n$100"
    assert count == 1


def test_invalid_and_missing_selectors_are_distinct() -> None:
    with pytest.raises(ValueError, match="INVALID_SELECTOR"):
        extract_html(b"<p>x</p>", selector="[", ignore_selectors=[])
    with pytest.raises(LookupError, match="SELECTOR_NOT_FOUND"):
        extract_html(b"<p>x</p>", selector=".missing", ignore_selectors=[])


def test_first_candidate_is_real_and_diff_is_measured() -> None:
    before = make_candidate(
        MonitorType.TEXT, b"<p>Hello world</p>", selector=None, ignore_selectors=[], ignore_regexes=[]
    )
    after = make_candidate(
        MonitorType.TEXT, b"<p>Hello there</p>", selector=None, ignore_selectors=[], ignore_regexes=[]
    )
    score, diff = text_difference(before.text or "", after.text or "")
    assert before.content_hash != after.content_hash
    assert score > 0
    assert "-Hello world" in str(diff["unified"])
