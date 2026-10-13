from __future__ import annotations

import re

import numpy as np
import pandas as pd

from retailpulse.ingestion.reader import COLUMN_MAP, SchemaError

SALE = "sale"
RETURN = "return"
EXCLUDED = "excluded"

INVALID_FIELD = "missing_or_invalid_field"
INVALID_DATE = "invalid_date"
INVALID_INVOICE = "invalid_invoice_number"
NON_PRODUCT = "non_product_code"
INCONSISTENT_CANCELLATION = "inconsistent_cancellation"
NON_POSITIVE_QUANTITY = "non_positive_quantity"
NON_POSITIVE_PRICE = "non_positive_price"
DUPLICATE = "duplicate_line"

EXCLUSION_REASONS = (
    INVALID_FIELD,
    INVALID_DATE,
    INVALID_INVOICE,
    NON_PRODUCT,
    INCONSISTENT_CANCELLATION,
    NON_POSITIVE_QUANTITY,
    NON_POSITIVE_PRICE,
    DUPLICATE,
)

NON_PRODUCT_CODES = frozenset(
    {"POST", "DOT", "M", "D", "S", "B", "C2", "BANK CHARGES", "AMAZONFEE", "CRUK", "PADS"}
)
NON_PRODUCT_PREFIXES = ("GIFT_",)

INVOICE_PATTERN = re.compile(r"C?\d{6}")
EARLIEST_PLAUSIBLE_DATE = pd.Timestamp("2000-01-01")

BUSINESS_KEY = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
]

OUTPUT_COLUMNS = [
    "source_row",
    *BUSINESS_KEY,
    "line_amount",
    "is_cancellation",
    "is_duplicate",
    "has_customer_id",
    "line_type",
    "exclusion_reason",
]


def _as_text(series: pd.Series, upper: bool = False) -> pd.Series:
    def convert(value: object) -> object:
        if pd.isna(value):
            return pd.NA
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        text = " ".join(str(value).split())
        if not text:
            return pd.NA
        return text.upper() if upper else text

    return series.map(convert).astype("string")


def _as_integer(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype("float64")
    whole = numeric.where(np.isfinite(numeric) & (numeric == np.floor(numeric)))
    return whole.astype("Int64")


def standardise_types(raw: pd.DataFrame) -> pd.DataFrame:
    """Convert raw text columns to analysis types. Unparseable values become missing."""
    required = ["source_row", *COLUMN_MAP.values()]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise SchemaError(f"Input is missing required columns: {', '.join(missing)}")

    typed = pd.DataFrame(index=raw.index)
    typed["source_row"] = raw["source_row"].astype("int64")
    typed["invoice_no"] = _as_text(raw["invoice_no"], upper=True)
    typed["stock_code"] = _as_text(raw["stock_code"], upper=True)
    typed["description"] = _as_text(raw["description"])
    typed["quantity"] = _as_integer(raw["quantity"])
    typed["invoice_date"] = pd.to_datetime(
        raw["invoice_date"], errors="coerce", format="mixed"
    ).astype("datetime64[us]")
    typed["unit_price"] = pd.to_numeric(raw["unit_price"], errors="coerce").astype("float64")
    typed["customer_id"] = _as_integer(raw["customer_id"])
    typed["country"] = _as_text(raw["country"])
    return typed


def flag_duplicates(typed: pd.DataFrame) -> pd.Series:
    """Flag every repeat of an identical business record, keeping the first occurrence."""
    ordered = typed.sort_values("source_row", kind="stable")
    return ordered.duplicated(subset=BUSINESS_KEY, keep="first").reindex(typed.index)


def classify_transactions(raw: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Classify every raw line as a sale, a return or an excluded record.

    No rows are dropped. Each row receives a ``line_type`` and, when excluded, the first
    matching ``exclusion_reason`` in the precedence order of ``EXCLUSION_REASONS``.
    """
    typed = standardise_types(raw)
    as_of = as_of or pd.Timestamp.now()

    is_cancellation = typed["invoice_no"].str.startswith("C").fillna(False).astype(bool)
    is_duplicate = flag_duplicates(typed).astype(bool)
    quantity = typed["quantity"]
    price = typed["unit_price"]
    date = typed["invoice_date"]
    stock_code = typed["stock_code"].fillna("")

    conditions = {
        INVALID_FIELD: (
            typed["invoice_no"].isna() | typed["stock_code"].isna() | quantity.isna() | price.isna()
        ),
        INVALID_DATE: date.isna() | (date < EARLIEST_PLAUSIBLE_DATE) | (date > as_of),
        INVALID_INVOICE: ~typed["invoice_no"].fillna("").str.fullmatch(INVOICE_PATTERN),
        NON_PRODUCT: (
            stock_code.isin(NON_PRODUCT_CODES) | stock_code.str.startswith(NON_PRODUCT_PREFIXES)
        ),
        INCONSISTENT_CANCELLATION: is_cancellation & (quantity >= 0).fillna(False),
        NON_POSITIVE_QUANTITY: ~is_cancellation & (quantity <= 0).fillna(False),
        NON_POSITIVE_PRICE: (price <= 0).fillna(False),
        DUPLICATE: is_duplicate,
    }
    masks = [
        conditions[reason].to_numpy(dtype=bool, na_value=False) for reason in EXCLUSION_REASONS
    ]
    reason = np.select(masks, EXCLUSION_REASONS, default="")
    excluded = reason != ""

    classified = typed.copy()
    classified["line_amount"] = (quantity.astype("float64") * price).round(4)
    classified["is_cancellation"] = is_cancellation
    classified["is_duplicate"] = is_duplicate
    classified["has_customer_id"] = typed["customer_id"].notna()
    classified["line_type"] = np.where(excluded, EXCLUDED, np.where(is_cancellation, RETURN, SALE))
    classified["exclusion_reason"] = pd.Series(reason, index=typed.index).where(excluded, pd.NA)
    classified["line_type"] = classified["line_type"].astype("string")
    classified["exclusion_reason"] = classified["exclusion_reason"].astype("string")
    return classified[OUTPUT_COLUMNS]
