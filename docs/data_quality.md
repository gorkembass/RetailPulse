# Data quality

## Approach

The raw file is never edited and no row is deleted. The cleaning step converts types, then gives every row a `line_type` (`sale`, `return` or `excluded`) and, when excluded, an `exclusion_reason`. All 541,909 rows are loaded into `staging.transactions` with those labels, so every exclusion can be counted, valued and reversed.

Rules live in `src/retailpulse/cleaning/rules.py`. They are verified independently in SQL by `sql/analysis/06_data_quality.sql`.

## Source profile

Measured on the UCI Online Retail file (SHA-256 `43465a06…424676d`).

| Check | Result |
|---|---|
| Rows | 541,909 |
| Invoice date range | 2010-12-01 08:26 to 2011-12-09 12:50 |
| Missing `CustomerID` | 135,080 rows (24.9%) |
| Missing `Description` | 1,454 rows, all with a unit price of zero |
| Exact duplicate rows | 5,268 |
| Cancellation lines (`InvoiceNo` starts with `C`) | 9,288 |
| Negative quantity outside a cancellation | 1,336, all with a unit price of zero |
| Unit price of zero | 2,515 |
| Negative unit price | 2 (`Adjust bad debt`) |
| Non-merchandise stock codes | 2,947 rows across 15 codes |
| Unparseable dates, quantities or prices | 0 |
| Stock codes with more than one description | 207 of 3,812 valid products |

## Type conversion

| Column | Conversion | Invalid values |
|---|---|---|
| `invoice_no`, `stock_code` | Text, trimmed, upper-cased; whole-number floats lose the `.0` | Empty becomes missing |
| `description`, `country` | Text, whitespace collapsed | Empty becomes missing |
| `quantity`, `customer_id` | Nullable integer | Non-numeric or fractional becomes missing |
| `unit_price` | Float | Non-numeric becomes missing |
| `invoice_date` | Timestamp | Unparseable becomes missing |

The reader loads every column as text or as the native spreadsheet object, so malformed values reach the rules instead of being coerced silently on read.

## Classification rules

Rules are evaluated in this order. A row is reported under the first rule it breaks.

| # | Reason code | Rule | Why | Rows | Signed value |
|---|---|---|---|---:|---:|
| 1 | `missing_or_invalid_field` | Invoice number, stock code, quantity or price is missing or invalid | The line cannot be valued or attributed | 0 | £0 |
| 2 | `invalid_date` | Date is missing, unparseable, before 2000 or in the future | The line cannot be placed in time | 0 | £0 |
| 3 | `invalid_invoice_number` | Invoice number is not six digits with an optional `C` prefix | The three `A`-prefixed rows are bad-debt adjustments, not sales | 3 | −£11,062 |
| 4 | `non_product_code` | Stock code is postage, carriage, a fee, a discount, a manual adjustment, a sample or a gift voucher | Not merchandise; mixing it in distorts product and basket metrics | 2,947 | −£33,899 |
| 5 | `inconsistent_cancellation` | Credit note with a non-negative quantity | Contradictory record | 0 | £0 |
| 6 | `non_positive_quantity` | Zero or negative quantity outside a credit note | Stock write-offs (`damaged`, `thrown away`), all at price zero | 1,336 | £0 |
| 7 | `non_positive_price` | Unit price of zero or less | Free items, samples and corrections carry no revenue | 1,161 | £0 |
| 8 | `duplicate_line` | Exact repeat of an earlier row across all eight source columns | See the sensitivity section below | 5,257 | £21,391 |

Rows that pass every rule are a `return` when the invoice is a credit note and a `sale` otherwise.

| Line type | Rows | Share of rows | Signed value |
|---|---:|---:|---:|
| `sale` | 522,537 | 96.4% | £10,247,219 |
| `return` | 8,668 | 1.6% | −£475,901 |
| `excluded` | 10,704 | 2.0% | −£23,570 |

The `is_duplicate` flag is set on all 5,268 duplicate rows. Only 5,257 are reported under `duplicate_line` because 11 of them break an earlier rule first. The SQL query `duplicate_recheck` recomputes duplicates with `ROW_NUMBER()` and finds the same 5,268 rows, with zero disagreements.

## Rules that are not exclusions

**Missing customer ID.** These rows are kept as sales and flagged with `has_customer_id = false`. Removing them, a common shortcut with this dataset, would discard £1,509,992 of revenue (14.7%). They are left out only where a customer is required: RFM, cohorts, new versus returning and repeat purchase rate.

**Missing description.** Not a reason to exclude. `dim_product` takes the most frequent description for each stock code, falling back to `UNKNOWN`. In practice every row with a missing description is excluded anyway because its price is zero.

**Extreme quantities.** Not capped or removed. The two largest orders (80,995 and 74,215 units) are real invoices that were cancelled in full within minutes. Both the sale and the return are kept, so they cancel out in net revenue. They are the reason product rankings use net revenue.

## Effect on results

### Sensitivity of gross revenue

From `06_data_quality.sql` → `rule_sensitivity`.

| Treatment | Gross revenue | Difference |
|---|---:|---:|
| Base case | £10,247,219 | |
| Keep duplicate lines | £10,271,433 | +£24,214 (+0.24%) |
| Count positive non-product lines as revenue | £10,631,409 | +£384,189 (+3.75%) |
| Drop rows without a customer ID | £8,737,228 | −£1,509,992 (−14.74%) |

**Duplicates** are the judgement call. Identical lines on one invoice could be an item scanned twice or an export fault, and the source cannot tell them apart. The base case excludes them; the effect on revenue is a quarter of a percent either way.

**Non-product lines** are the larger definitional choice. Including postage would raise revenue by 3.75% and would not be merchandise revenue.

**Missing customers** are the rule with the largest potential effect, which is why the base case keeps those rows.

### Customer coverage

| | With customer ID | Without |
|---|---:|---:|
| Sale lines | 391,150 (74.9%) | 131,387 (25.1%) |
| Orders | 18,402 (93.1%) | 1,371 (6.9%) |
| Gross revenue | £8,737,228 (85.3%) | £1,509,992 (14.7%) |

Orders without a customer ID are few but large: 6.9% of orders carry 25.1% of lines. The share of revenue without a customer varies by month from 8.7% (September 2011) to 27.1% (December 2010) (`missing_customer_by_month`). Customer-level metrics are therefore understated unevenly over time, and month-to-month changes in new or returning revenue should be read with that in mind.

### Returns

Returns reduce gross revenue by 4.6% overall, but two credit notes account for £245,653 of the £475,901. Excluding the largest credit note in each month, the monthly return rate stays between 0.9% and 2.9% (`returns_impact_by_month`).

## Derived attributes

**Product category** is not in the source. `cleaning/products.py` assigns one of eight categories from ordered keyword rules matched as whole words against the description; the first matching rule wins. Unmatched products become `Other` (396 products, 4.5% of gross revenue). The rules are heuristic and some assignments are debatable, for example a ceramic storage jar lands in Bags & Storage because that rule is evaluated before Kitchen & Dining. Category figures are suitable for a broad view of the mix, not for decisions about a specific range.

## Warehouse integrity

The `warehouse_reconciliation` query confirms after each load that:

- `analytics.fact_sales` holds exactly the 531,205 non-excluded staging rows;
- its total (`£9,771,318.16`) equals the staging total for those rows;
- no fact row lacks a product.

`fact_sales` also enforces the rules structurally: `line_type` is restricted to `sale` or `return`, `unit_price` must be positive, and the sign of `quantity` must match the line type.
