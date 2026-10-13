from __future__ import annotations

from functools import partial

import streamlit as st

from retailpulse.cleaning.rules import EXCLUDED

from data_access import MARKETS, filter_transactions, load_dataset
from views import customers, data_quality, overview, products

st.set_page_config(page_title="RetailPulse", page_icon=":material/monitoring:", layout="wide")

dataset = load_dataset()
if dataset is None:
    st.title("RetailPulse")
    st.error(
        "No processed data found. Run `retailpulse ingest` and `retailpulse clean` "
        "(or `retailpulse run`) to build the processed layer, then reload this page."
    )
    st.stop()

valid_dates = dataset.transactions.loc[
    dataset.transactions["line_type"] != EXCLUDED, "invoice_date"
].dt.date
first_day, last_day = valid_dates.min(), valid_dates.max()

with st.sidebar:
    st.header("Filters")
    selected_range = st.date_input(
        "Invoice date", value=(first_day, last_day), min_value=first_day, max_value=last_day
    )
    market = st.radio("Market", MARKETS)
    st.divider()
    if dataset.metadata.get("is_synthetic"):
        st.warning(
            "Synthetic data. Figures do not describe a real business.", icon=":material/science:"
        )
    else:
        st.caption(
            "Source: UCI Online Retail (CC BY 4.0). A UK-based online gift retailer, "
            "1 Dec 2010 to 9 Dec 2011. Amounts in GBP."
        )

if len(selected_range) != 2:
    st.info("Select both a start and an end date.")
    st.stop()

transactions = filter_transactions(
    dataset.transactions, selected_range[0], selected_range[1], market
)

navigation = st.navigation(
    [
        st.Page(
            partial(overview.render, transactions),
            title="Sales overview",
            icon=":material/monitoring:",
            url_path="overview",
            default=True,
        ),
        st.Page(
            partial(products.render, transactions, dataset.products),
            title="Products",
            icon=":material/inventory_2:",
            url_path="products",
        ),
        st.Page(
            partial(customers.render, transactions),
            title="Customers",
            icon=":material/group:",
            url_path="customers",
        ),
        st.Page(
            partial(data_quality.render, transactions),
            title="Data quality",
            icon=":material/fact_check:",
            url_path="data-quality",
        ),
    ]
)
navigation.run()
