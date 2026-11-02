"""Provisional schema v1. Decimal arithmetic only; no binary float conversions."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
import uuid

GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "orders-v1-provisional"
CENT = Decimal("0.01")
STATUSES = ("completed", "pending", "failed", "refunded")
LOCATIONS = (
    ("MX", "Chiapas", "Tuxtla Gutierrez", "29000", "-93.1150", "16.7530"),
    ("US", "Texas", "Austin", "78701", "-97.7431", "30.2672"),
    ("CO", "Bogota", "Bogota", "110111", "-74.0721", "4.7110"),
    ("ES", "Madrid", "Madrid", "28001", "-3.7038", "40.4168"),
    ("AR", "Buenos Aires", "Buenos Aires", "C1000", "-58.3816", "-34.6037"),
)
CATEGORIES = ("electronics", "home", "books", "clothing", "sports", "food")
NAMESPACE = uuid.UUID("7fc8d0bf-0738-5a48-9f18-d859d0993090")


class DataError(ValueError):
    """Invalid file, schema or logical data."""


def json_text(value, canonical=False):
    """Stable JSON numeric tokens, preserving decimals; canonical normalizes scale."""
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DataError("Non-finite number")
        if canonical:
            text = format(value, "f")
            return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"
        return format(value, "f")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(json_text(x, canonical) for x in value) + "]"
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return "{" + ",".join(json_text(k) + ":" + json_text(value[k], canonical) for k in sorted(value)) + "}"
    raise DataError(f"Unsupported JSON type: {type(value).__name__}")


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise DataError(f"Duplicate JSON field: {k}")
        result[k] = v
    return result


def parse_json(text):
    def invalid(value):
        raise DataError(f"Invalid JSON number: {value}")
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=invalid, object_pairs_hook=_pairs)
    except (ValueError, TypeError, RecursionError) as exc:
        raise DataError("Invalid JSON: " + str(exc)) from exc


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise DataError("Timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise DataError("Invalid calendar date") from exc


def valid_uuid(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError) as exc:
        raise DataError("UUID must be a canonical lower-case string") from exc
    return value


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def totals(items):
    subtotal = discount = tax = Decimal("0.00")
    for item in items:
        gross = item["price"] * item["qty"]
        reduction = sum(item["discounts"], Decimal("0.00"))
        subtotal += gross
        discount += reduction
        tax += money((gross - reduction) * item["tax_pct"] / 100)
    return {"subtotal": money(subtotal), "discount": money(discount), "tax": money(tax),
            "final_total": money(subtotal - discount + tax)}


class StableRng:
    """Versioned SHA-256 counter stream; no dependency on Python random internals."""
    def __init__(self, seed):
        self.key = str(seed).encode("ascii") + b":"
        self.counter = 0
        self.pool = b""

    def below(self, bound):
        if not 0 < bound <= 2**32:
            raise DataError("Invalid PRNG bound")
        ceiling = 2**32 - (2**32 % bound)
        while True:
            if len(self.pool) < 4:
                self.pool = hashlib.sha256(self.key + str(self.counter).encode("ascii")).digest()
                self.counter += 1
            number = int.from_bytes(self.pool[:4], "big")
            self.pool = self.pool[4:]
            if number < ceiling:
                return number % bound

    def choose(self, values):
        return values[self.below(len(values))]


def documents(seed, count, start, end, layout):
    rng = StableRng(seed)
    first = timestamp(start)
    seconds = int((timestamp(end) - first).total_seconds())
    if seconds <= 0 or seconds > 2**32:
        raise DataError("Date interval must be positive and <= 2**32 seconds")
    for index in range(count):
        uid = lambda name: str(uuid.uuid5(NAMESPACE, f"{seed}:{name}"))
        loc = rng.choose(LOCATIONS)
        items = []
        for _ in range(1 + rng.below(5)):
            band = rng.below(100)
            cents = (1 + rng.below(5000) if band < 55 else
                     5001 + rng.below(45000) if band < 90 else 50001 + rng.below(150000))
            price = Decimal(cents).scaleb(-2)
            qty = 1 + rng.below(6)
            reductions = []
            if rng.below(100) < 20:
                reductions = [money(price * qty * Decimal(1 + rng.below(10)) / 100)]
            items.append({"sku": f"SKU-{rng.below(10000):05}", "category": rng.choose(CATEGORIES),
                          "brand": f"brand-{rng.below(30):02}", "qty": qty, "price": price,
                          "tax_pct": Decimal(rng.choose((0, 8, 16))).quantize(CENT), "discounts": reductions})
        computed = totals(items)
        state = rng.below(100)
        payment = {"method": rng.choose(("card", "transfer", "cash", "wallet")),
                   "status": "completed" if state < 70 else "pending" if state < 85 else "failed" if state < 95 else "refunded",
                   "transaction_id": uid(f"transaction:{index}"), "gateway_latency_ms": 10 + rng.below(1491),
                   "totals": computed}
        if layout == "totals-and-alias":
            payment["final_total"] = computed["final_total"]
        yield {
            "order_id": uid(f"order:{index}"),
            "timestamp": datetime.fromtimestamp(int(first.timestamp()) + rng.below(seconds), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "customer": {"id": uid(f"customer:{rng.below(100000)}"), "tier": rng.choose(("standard", "standard", "silver", "gold")),
                         "segment": rng.choose(("retail", "business")),
                         "geo": {"country": loc[0], "state": loc[1], "city": loc[2], "zip": loc[3],
                                 "coordinates": [(Decimal(loc[4]) + Decimal(rng.below(40001)-20000).scaleb(-6)).quantize(Decimal("0.000001")),
                                                 (Decimal(loc[5]) + Decimal(rng.below(40001)-20000).scaleb(-6)).quantize(Decimal("0.000001"))]}},
            "items": items, "payment": payment,
            "metadata": {"channel": rng.choose(("web", "mobile", "store")), "user_agent": rng.choose(("synthetic-browser/1", "synthetic-mobile/1")),
                         "session_id": uid(f"session:{index}"), "flags": {"gift": rng.below(10) == 0, "priority": rng.below(20) == 0}}
        }


def _keys(obj, expected, label):
    if not isinstance(obj, dict) or set(obj) != set(expected.split()):
        raise DataError(f"Fields differ in {label}")


def _text(value):
    if not isinstance(value, str) or not value or "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise DataError("Expected nonempty interoperable UTF8 string without NUL")


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise DataError("Integer out of range")


def _number(value, low, high, places=2):
    if type(value) not in (int, Decimal) or not Decimal(value).is_finite():
        raise DataError("Expected exact finite number (not float/bool/string)")
    number = Decimal(value)
    if not low <= number <= high or number != number.quantize(Decimal(1).scaleb(-places)):
        raise DataError("Number outside contract range/scale")


def validate_order(doc, layout="totals-and-alias"):
    _keys(doc, "order_id timestamp customer items payment metadata", "order")
    valid_uuid(doc["order_id"])
    timestamp(doc["timestamp"])
    customer = doc["customer"]
    _keys(customer, "id tier segment geo", "customer")
    valid_uuid(customer["id"])
    if customer["tier"] not in ("standard", "silver", "gold") or customer["segment"] not in ("retail", "business"):
        raise DataError("Invalid customer classification")
    geo = customer["geo"]
    _keys(geo, "country state city zip coordinates", "geo")
    if tuple(geo[k] for k in ("country", "state", "city", "zip")) not in [loc[:4] for loc in LOCATIONS]:
        raise DataError("Unknown synthetic location")
    if not isinstance(geo["coordinates"], list) or len(geo["coordinates"]) != 2:
        raise DataError("Expected longitude/latitude pair")
    _number(geo["coordinates"][0], -180, 180, 6)
    _number(geo["coordinates"][1], -90, 90, 6)
    if not isinstance(doc["items"], list) or not 1 <= len(doc["items"]) <= 5:
        raise DataError("Expected 1..5 items")
    for item in doc["items"]:
        _keys(item, "sku category brand qty price tax_pct discounts", "item")
        _text(item["sku"]); _text(item["brand"])
        if item["category"] not in CATEGORIES:
            raise DataError("Invalid category")
        _integer(item["qty"], 1, 6)
        _number(item["price"], CENT, 2000)
        if type(item["tax_pct"]) not in (int, Decimal) or item["tax_pct"] not in (0, 8, 16):
            raise DataError("Invalid tax")
        if not isinstance(item["discounts"], list) or len(item["discounts"]) > 1:
            raise DataError("Invalid discounts list")
        for reduction in item["discounts"]:
            _number(reduction, 0, item["price"] * item["qty"])
    payment = doc["payment"]
    fields = "method status transaction_id gateway_latency_ms totals" + (" final_total" if layout == "totals-and-alias" else "")
    _keys(payment, fields, "payment")
    if payment["status"] not in STATUSES or payment["method"] not in ("card", "transfer", "cash", "wallet"):
        raise DataError("Invalid payment enum")
    valid_uuid(payment["transaction_id"])
    _integer(payment["gateway_latency_ms"], 10, 1500)
    _keys(payment["totals"], "subtotal discount tax final_total", "totals")
    for key, value in totals(doc["items"]).items():
        _number(payment["totals"][key], 0, 100000)
        if payment["totals"][key] != value:
            raise DataError(f"Incorrect totals.{key}")
    if layout == "totals-and-alias":
        _number(payment["final_total"], 0, 100000)
        if payment["final_total"] != payment["totals"]["final_total"]:
            raise DataError("final_total alias differs")
    metadata = doc["metadata"]
    _keys(metadata, "channel user_agent session_id flags", "metadata")
    if metadata["channel"] not in ("web", "mobile", "store"):
        raise DataError("Invalid channel")
    _text(metadata["user_agent"]); valid_uuid(metadata["session_id"])
    _keys(metadata["flags"], "gift priority", "flags")
    if not all(type(v) is bool for v in metadata["flags"].values()):
        raise DataError("Expected boolean flags")
    return doc
