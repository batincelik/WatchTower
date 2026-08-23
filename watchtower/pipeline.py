import difflib
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from watchtower.models import MonitorType


@dataclass(frozen=True)
class Candidate:
    content_hash: str
    text: str | None = None
    html: str | None = None
    numeric_value: Decimal | None = None
    availability_state: str | None = None


def normalize_text(value: str, ignore_regexes: list[str] | None = None) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    for pattern in ignore_regexes or []:
        # User patterns are length-bounded at the API. This substitution operates on
        # already size-bounded responses; a future RE2 backend can strengthen this.
        value = re.sub(pattern, "", value)
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def extract_html(
    body: bytes,
    *,
    selector: str | None,
    ignore_selectors: list[str],
) -> tuple[str, str, int]:
    soup = BeautifulSoup(body, "html.parser")
    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    try:
        for ignored in ignore_selectors:
            for node in soup.select(ignored):
                node.decompose()
        matches = soup.select(selector) if selector else [soup]
    except Exception as exc:
        raise ValueError("INVALID_SELECTOR") from exc
    if selector and not matches:
        raise LookupError("SELECTOR_NOT_FOUND")
    html = "\n".join(str(node) for node in matches)
    text = "\n".join(node.get_text("\n") for node in matches)
    return html, text, len(matches)


def parse_price(value: str) -> Decimal | None:
    match = re.search(r"[-+]?\d[\d\s.,'’]*", value.replace("\u00a0", " "))
    if not match:
        return None
    raw = re.sub(r"[\s'’]", "", match.group())
    dot, comma = raw.rfind("."), raw.rfind(",")
    if dot >= 0 and comma >= 0:
        decimal_sep = "." if dot > comma else ","
    elif comma >= 0:
        tail = len(raw) - comma - 1
        decimal_sep = "," if tail in {1, 2} else ""
    elif dot >= 0:
        tail = len(raw) - dot - 1
        # A single dot followed by three digits is predictably interpreted as a
        # thousands separator (e.g. 1.299 TL).
        decimal_sep = "." if tail in {1, 2} else ""
    else:
        decimal_sep = ""
    if decimal_sep:
        thousands = "," if decimal_sep == "." else "."
        normalized = raw.replace(thousands, "").replace(decimal_sep, ".")
    else:
        normalized = raw.replace(",", "").replace(".", "")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def make_candidate(
    monitor_type: MonitorType,
    body: bytes,
    *,
    selector: str | None,
    ignore_selectors: list[str],
    ignore_regexes: list[str],
    availability_rules: dict[str, str] | None = None,
) -> Candidate:
    html, extracted, _ = extract_html(body, selector=selector, ignore_selectors=ignore_selectors)
    text = normalize_text(extracted, ignore_regexes)
    numeric = parse_price(text) if monitor_type == MonitorType.PRICE else None
    if monitor_type == MonitorType.PRICE and numeric is None:
        raise ValueError("PRICE_PARSE_FAILED")
    availability = None
    if monitor_type == MonitorType.AVAILABILITY:
        rules = availability_rules or {}
        lowered = text.casefold()
        if rules.get("in_stock_text", "").casefold() in lowered and rules.get("in_stock_text"):
            availability = "in_stock"
        elif rules.get("out_of_stock_text", "").casefold() in lowered and rules.get("out_of_stock_text"):
            availability = "out_of_stock"
        else:
            availability = "unknown"
    representation = html if monitor_type == MonitorType.HTML else text
    if monitor_type == MonitorType.STATUS:
        representation = ""
    digest = hashlib.sha256(representation.encode()).hexdigest()
    return Candidate(
        content_hash=digest,
        text=None if monitor_type == MonitorType.HTML else text,
        html=html if monitor_type == MonitorType.HTML else None,
        numeric_value=numeric,
        availability_state=availability,
    )


def text_difference(previous: str, current: str) -> tuple[Decimal, dict[str, object]]:
    ratio = difflib.SequenceMatcher(None, previous, current, autojunk=False).ratio()
    score = Decimal(str(round((1 - ratio) * 100, 4)))
    lines = list(difflib.unified_diff(previous.splitlines(), current.splitlines(), lineterm=""))
    return score, {"unified": "\n".join(lines[:500])}
