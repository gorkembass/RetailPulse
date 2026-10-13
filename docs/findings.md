# Analysis findings

Results from the UCI Online Retail dataset: a UK-based online retailer of gift and homeware items, many of whose customers are wholesalers, from 1 December 2010 to 9 December 2011. Amounts are in pounds sterling.

Every figure below was produced by the pipeline in this repository and is reproducible with `retailpulse run`. Figures come from `data/processed/sql_results/`; the query that produces each one is named in brackets. Metric definitions are in [kpi_dictionary.md](kpi_dictionary.md).

## Headline figures

| Metric | Value |
|---|---:|
| Gross revenue | £10,247,219 |
| Return value | £475,901 |
| Net revenue | £9,771,318 |
| Orders | 19,773 |
| Average order value | £518.24 |
| Median order value | £302.20 |
| Units sold | 5,561,384 |
| Identified customers | 4,334 |
| Return rate | 4.6% |
| Gross revenue with a customer ID | 85.3% |

(`01_sales_overview.sql` → `headline_kpis`)

## 1. Revenue is seasonal and peaks in November

| Month | Orders | Gross revenue | Per trading day | Return rate |
|---|---:|---:|---:|---:|
| Dec 2010 | 1,550 | £775,638 | £38,782 | 2.3% |
| Jan 2011 | 1,081 | £670,380 | £27,933 | 13.7% |
| Feb 2011 | 1,093 | £507,800 | £21,158 | 1.6% |
| Mar 2011 | 1,440 | £689,834 | £25,549 | 1.5% |
| Apr 2011 | 1,235 | £515,378 | £24,542 | 6.5% |
| May 2011 | 1,668 | £739,953 | £29,598 | 1.2% |
| Jun 2011 | 1,525 | £737,559 | £28,368 | 1.9% |
| Jul 2011 | 1,452 | £688,219 | £26,470 | 1.7% |
| Aug 2011 | 1,339 | £724,217 | £27,854 | 3.2% |
| Sep 2011 | 1,818 | £1,028,320 | £39,551 | 1.7% |
| Oct 2011 | 2,005 | £1,103,314 | £42,435 | 3.8% |
| Nov 2011 | 2,751 | £1,452,116 | £55,851 | 1.7% |
| Dec 2011 (to 9th) | 816 | £614,491 | £76,811 | 28.3% |

(`05_revenue_trends.sql` → `monthly_revenue_trend`)

- Revenue from September to November 2011 was £3.58M, 35% of the total, consistent with trade customers stocking up before Christmas. November was 2.9 times February.
- December 2011 covers eight trading days. Its total is not comparable with other months, and its per-trading-day figure is inflated by one £168,470 order that was cancelled the same day.
- The retailer recorded no sales on any Saturday. Thursday was the strongest day (£2.13M) and Sunday the weakest trading day (£0.80M) (`weekday_hour_pattern`).
- 84% of revenue was invoiced between 09:00 and 15:59.

**Implication:** stock and staffing plans need to be in place by late August. Month-on-month comparisons should use revenue per trading day.

## 2. Returns are small, apart from two cancelled orders

The overall return rate is 4.6%, but it is not evenly spread.

| Month | Return value | Largest credit note | Return rate | Excluding largest |
|---|---:|---:|---:|---:|
| Jan 2011 | £91,525 | £77,184 | 13.7% | 2.1% |
| Apr 2011 | £33,316 | £22,998 | 6.5% | 2.0% |
| Dec 2011 | £174,091 | £168,470 | 28.3% | 0.9% |

(`05_revenue_trends.sql` → `returns_impact_by_month`)

- Two credit notes, each reversing a single very large order within minutes of it being placed, account for £245,653 of the £475,901 returned (52%).
- Excluding the largest credit note in each month, the monthly return rate stays between 0.9% and 2.9%.
- These reversed orders also distort gross figures. The best day by gross revenue, 9 December 2011, and the second-ranked product by gross revenue, `PAPER CRAFT , LITTLE BIRDIE`, both exist only because of an order that netted to zero.

**Implication:** the underlying return rate is about 2%, not 4.6%. Order-entry errors on bulk quantities are a process issue rather than a product-quality one. Reports should rank on net revenue.

## 3. Sales are concentrated in a small part of the range

- The top 10% of products (380 of 3,798 sold) generate 61.4% of gross revenue. The bottom half generate 4.1% (`revenue_concentration`).
- 816 products (21.5%) account for 80% of gross revenue.
- By derived category, Home Decor (24.5%), Bags & Storage (23.0%) and Kitchen & Dining (22.6%) make up 70% of revenue (`category_performance`).
- Stationery & Gift Wrap has a 23.5% return rate, but that is the single cancelled `PAPER CRAFT` order. No category has a structurally high return rate.

Top five products by net revenue (`product_performance`):

| Product | Net revenue | Orders |
|---|---:|---:|
| REGENCY CAKESTAND 3 TIER | £164,459 | 1,988 |
| WHITE HANGING HEART T-LIGHT HOLDER | £99,791 | 2,265 |
| PARTY BUNTING | £98,244 | 1,685 |
| JUMBO BAG RED RETROSPOT | £92,176 | 2,089 |
| RABBIT NIGHT LIGHT | £66,662 | 994 |

**Implication:** availability of roughly 800 products protects four-fifths of revenue. The 1,900 products in the bottom half are candidates for a range review. Category figures rest on keyword-derived categories and should be treated as indicative.

## 4. The business depends on the UK and on a few large overseas accounts

| Market | Orders | Customers | Gross revenue | Share | Average order value |
|---|---:|---:|---:|---:|---:|
| United Kingdom | 17,901 | 3,916 | £8,724,444 | 85.1% | £487 |
| International | 1,872 | 418 | £1,522,776 | 14.9% | £813 |

(`01_sales_overview.sql` → `domestic_vs_international`, `revenue_by_country`)

- International orders are 67% larger on average than UK orders.
- The Netherlands (£283,889), EIRE (£270,851) and Australia (£138,104) rank second, third and sixth by revenue, yet have nine, three and nine identified customers. Germany (94 customers) and France (87) are the only broad overseas customer bases.

**Implication:** revenue from the Netherlands, EIRE and Australia is account risk, not market strength. Germany and France are the markets where customer acquisition has demonstrably worked.

## 5. A quarter of customers generate two-thirds of revenue

| Segment | Customers | Share of customers | Share of net revenue | Avg. orders | Avg. recency (days) |
|---|---:|---:|---:|---:|---:|
| Champions | 1,006 | 23.2% | 66.5% | 10.8 | 13 |
| Loyal Customers | 276 | 6.4% | 8.7% | 6.3 | 48 |
| Hibernating | 562 | 13.0% | 5.9% | 2.3 | 162 |
| Potential Loyalists | 474 | 10.9% | 4.8% | 2.4 | 17 |
| At Risk | 214 | 4.9% | 4.6% | 5.5 | 128 |
| Lost | 979 | 22.6% | 4.2% | 1.0 | 221 |
| Needs Attention | 297 | 6.9% | 3.0% | 2.4 | 51 |
| Promising | 294 | 6.8% | 1.4% | 1.0 | 52 |
| New Customers | 232 | 5.4% | 0.9% | 1.0 | 19 |

(`03_customer_segmentation.sql` → `rfm_segment_summary`)

- The top decile of customers by revenue (434 customers) accounts for 61.4% of identified revenue (`customer_value_deciles`).
- 65.3% of identified customers ordered more than once; 34.7% ordered exactly once. The median customer placed two orders (`repeat_purchase_rate`).
- At Risk customers are few (214) but valuable: an average of £1,767 each and 5.5 orders, with no purchase for four months on average.
- From January 2011 onwards, returning customers generated 69% of gross revenue, new customers 17% and orders without a customer ID 14% (`new_vs_returning_by_month`).

**Implication:** the highest-return actions are retaining the 1,006 Champions and winning back the 214 At Risk customers (£378k of historical net revenue). The 526 customers in New Customers and Promising have ordered once; a second-order incentive is the cheapest route to growing the loyal base.

## 6. Retention is stable at about one in four

| Cohort | Size | Month 1 | Month 3 | Month 6 | Month 9 | Month 12 |
|---|---:|---:|---:|---:|---:|---:|
| Dec 2010 | 884 | 36.5% | 38.3% | 36.2% | 39.5% | 26.5% |
| Jan 2011 | 416 | 21.9% | 22.8% | 24.8% | 32.7% | |
| Feb 2011 | 380 | 18.7% | 28.7% | 25.5% | 30.5% | |
| Mar 2011 | 452 | 14.8% | 19.9% | 26.8% | 8.6% | |
| Jun 2011 | 242 | 17.4% | 26.4% | 9.5% | | |
| Sep 2011 | 299 | 23.4% | 11.4% | | | |

(`04_cohort_retention.sql` → `cohort_retention_matrix`; the full matrix is in the dashboard)

- Across all cohorts, 22.5% of customers order again in the month after their first purchase, rising to 27% by month six (`average_retention_by_period`). Retention does not decay over the year, which fits a base of trade customers who reorder on a regular cycle.
- The December 2010 cohort retains about 36%, well above later cohorts at 15% to 24% in their first month. This is at least partly an artefact: the data begins that month, so the cohort includes every long-standing customer who happened to order then.
- The last cell of each row falls in December 2011, which has eight trading days. Those values (8.6%, 9.5%, 11.4% above) are understated and should not be read as a decline.
- Every cohort acquired before August was more active in September to November than in its earlier months, so calendar seasonality is visible inside the retention curves.

**Implication:** cohorts from January 2011 onwards are the reliable baseline, at roughly 20% to 25% monthly activity. A new cohort falling clearly below that range would be an early warning.

## 7. Revenue is not profit

The dataset has no cost information, so profit is not reported. What can be said:

- £475,901 (4.6%) separates gross from net revenue.
- Lines excluded as non-merchandise include £221,520 of marketplace fees and £272,476 of postage charged to customers, neither of which is product revenue.
- Under assumed cost-of-goods ratios of 50%, 60% and 70%, gross margin on £9.77M of net revenue would be £4.89M, £3.91M or £2.93M (`revenue_vs_assumed_margin`). The £1.95M range between those scenarios is larger than any effect found elsewhere in this analysis, which is the point: the most valuable missing data is unit cost.

## Limitations

- **One year of data.** Seasonality is observed once and cannot be separated from growth. No year-on-year comparison is possible beyond nine days of December.
- **Left truncation.** Customers who first bought before December 2010 look new, which inflates early new-customer counts and the December 2010 cohort.
- **Partial final month.** December 2011 ends on the 9th.
- **Returns are not linked to sales.** Return rates compare credit notes issued in a period with sales in that period.
- **14.7% of revenue has no customer ID** and is absent from all customer-level results.
- **Categories are derived** from description keywords.
- **Mixed customer base.** Wholesale and retail customers cannot be told apart in the data, although order sizes suggest both are present. Averages therefore describe neither group well; medians and distributions are more informative.
- **No cost, marketing or web data.** Profitability, acquisition cost and conversion cannot be analysed.
