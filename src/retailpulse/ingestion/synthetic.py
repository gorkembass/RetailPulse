from __future__ import annotations

import numpy as np
import pandas as pd

RAW_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]

_CATALOGUE = [
    ("10001", "RED RETROSPOT LUNCH BAG", 1.65),
    ("10002", "JUMBO SHOPPER BAG VINTAGE", 2.08),
    ("10003", "WHITE HEART T-LIGHT HOLDER", 2.55),
    ("10004", "SCENTED CANDLE IN GLASS JAR", 3.75),
    ("10005", "CERAMIC TEA MUG BLUE", 2.95),
    ("10006", "SET OF 6 CAKE CASES", 0.55),
    ("10007", "VINTAGE CHRISTMAS BUNTING", 4.95),
    ("10008", "CHRISTMAS TREE DECORATION STAR", 0.85),
    ("10009", "BIRTHDAY CARD PACK OF 12", 2.10),
    ("10010", "GIFT WRAP ROLL FLORAL", 1.25),
    ("10011", "WOODEN ALPHABET TOY BLOCKS", 5.95),
    ("10012", "CHILDRENS JIGSAW PUZZLE FARM", 3.25),
    ("10013", "SILVER HEART NECKLACE", 6.50),
    ("10014", "GARDEN PLANT POT SMALL", 2.75),
    ("10015", "METAL DOOR SIGN WELCOME", 1.95),
    ("10016", "PICNIC BASKET WICKER", 9.95),
    ("10017", "ALARM CLOCK BAKELIKE GREEN", 3.75),
    ("10018", "PAPER NAPKINS POLKADOT", 0.85),
    ("10019", "REGENCY CAKESTAND 3 TIER", 12.75),
    ("10020", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
]

_COUNTRIES = ["United Kingdom", "Germany", "France", "EIRE", "Spain", "Netherlands"]
_COUNTRY_WEIGHTS = [0.80, 0.06, 0.05, 0.04, 0.03, 0.02]


def generate_synthetic_transactions(
    seed: int = 42, n_invoices: int = 1500, n_customers: int = 300
) -> pd.DataFrame:
    """Generate a deterministic dataset in the UCI Online Retail raw layout.

    The data is synthetic. It reproduces the data-quality problems of the real source
    (cancellations, duplicates, missing customers, zero prices, non-product lines) so the
    whole pipeline can be exercised offline and in CI.
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2023-01-02 08:00:00")
    customer_ids = np.arange(20001, 20001 + n_customers)
    customer_country = rng.choice(_COUNTRIES, size=n_customers, p=_COUNTRY_WEIGHTS)
    customer_weight = rng.pareto(1.5, size=n_customers) + 0.2
    customer_weight /= customer_weight.sum()

    invoice_days = np.sort(rng.integers(0, 365, size=n_invoices))
    rows: list[tuple] = []
    for position in range(n_invoices):
        invoice_no = str(600000 + position)
        timestamp = start + pd.Timedelta(
            days=int(invoice_days[position]), minutes=int(rng.integers(0, 540))
        )
        if rng.random() < 0.20:
            customer_id, country = np.nan, "United Kingdom"
        else:
            index = int(rng.choice(n_customers, p=customer_weight))
            customer_id, country = float(customer_ids[index]), customer_country[index]

        n_lines = int(rng.integers(1, 7))
        for item in rng.choice(len(_CATALOGUE), size=n_lines, replace=False):
            stock_code, description, price = _CATALOGUE[int(item)]
            quantity = int(
                rng.choice([1, 2, 3, 4, 6, 12, 24], p=[0.2, 0.2, 0.1, 0.1, 0.2, 0.15, 0.05])
            )
            rows.append(
                (
                    invoice_no,
                    stock_code,
                    description,
                    quantity,
                    timestamp,
                    price,
                    customer_id,
                    country,
                )
            )
        if country != "United Kingdom" and rng.random() < 0.5:
            rows.append((invoice_no, "POST", "POSTAGE", 1, timestamp, 18.0, customer_id, country))

    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)

    cancelled = frame[frame["StockCode"] != "POST"].sample(frac=0.03, random_state=seed)
    cancellations = cancelled.assign(
        InvoiceNo="C" + cancelled["InvoiceNo"],
        Quantity=-cancelled["Quantity"],
        InvoiceDate=cancelled["InvoiceDate"] + pd.Timedelta(days=3),
    )
    duplicates = frame.sample(frac=0.01, random_state=seed + 1)
    free_items = frame.sample(frac=0.005, random_state=seed + 2).assign(UnitPrice=0.0)
    write_offs = frame.sample(n=10, random_state=seed + 3).assign(
        InvoiceNo=[str(700000 + i) for i in range(10)],
        Description="damaged",
        Quantity=-5,
        UnitPrice=0.0,
        CustomerID=np.nan,
    )

    legacy_return = pd.DataFrame(
        [
            (
                "C799999",
                "10099",
                "DISCONTINUED GLASS VASE",
                -2,
                start + pd.Timedelta(days=10),
                4.25,
                float(customer_ids[0]),
                customer_country[0],
            )
        ],
        columns=RAW_COLUMNS,
    )

    combined = pd.concat([frame, cancellations, duplicates, free_items, write_offs, legacy_return])
    return combined.sort_values(["InvoiceDate", "InvoiceNo"], kind="stable").reset_index(drop=True)
