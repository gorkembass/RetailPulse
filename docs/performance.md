# Query performance and indexing

This document records how the indexes on `analytics.fact_sales` were chosen. No index is kept on the strength of an assumption: each one was measured with and without, and one candidate was removed because it made no difference.

## Method

`sql/performance/explain_analyze.sql` contains one probe per index. Each probe:

1. runs `EXPLAIN (ANALYZE, BUFFERS)` on a query with the index in place;
2. opens a transaction, drops the index, runs the same statement, and rolls back.

The rollback restores the index, so the script can be run repeatedly without changing the database. Parallel query is disabled for the session so that plans are comparable.

```bash
make explain
# or
docker compose exec -T postgres psql -U retailpulse -d retailpulse < sql/performance/explain_analyze.sql
```

How to read the output:

- **Plan shape first.** Check whether the scan on `fact_sales` is an index scan, a bitmap scan or a sequential scan. An index the planner does not choose has no benefit, only write and storage cost.
- **Buffers second.** `Buffers: shared hit=N` is the number of 8 kB pages touched. It is deterministic for a given plan and data, which makes it a more reliable comparison than time.
- **Execution time last.** Run the script at least three times and ignore the first run, which includes cache warm-up. Timings on a laptop vary by a few milliseconds between runs.
- **Rows removed by filter.** A large number next to a small result means the query read far more than it returned, which is what an index is for.

## Results

Environment: PostgreSQL 16.15 in Docker (`postgres:16-alpine`, default configuration: `shared_buffers` 128 MB, `work_mem` 4 MB) on an Apple M1 laptop. `fact_sales` has 531,205 rows and occupies 62 MB. Execution times are from three consecutive runs with a warm cache.

| Probe | Index | Plan with index | Pages with / without | Time with (ms) | Time without (ms) |
|---|---|---|---:|---:|---:|
| Orders of one customer (4,440 lines) | `idx_fact_sales_customer_id` | Bitmap index scan | 286 / 8,016 | 3.4, 2.6, 2.7 | 37.8, 34.7, 34.5 |
| One week of sales (6,615 lines) | `idx_fact_sales_date_key` | Index scan, incremental sort | 118 / 7,981 | 2.3, 2.2, 2.1 | 33.5, 33.9, 34.4 |
| Sales of one product (71 lines) | `idx_fact_sales_stock_code` | Bitmap index scan | 77 / 7,978 | 0.19, 0.16, 0.15 | 30.6, 30.5, 31.2 |
| Monthly revenue, whole table | none applies | Sequential scan, hash join | 7,983 | 134.9, 114.1, 113.6 | n/a |
| Order-level aggregate over `v_orders` | candidate on `invoice_no` | Sequential scan, hash aggregate | 7,975 / 7,975 | 107.6, 102.3, 103.2 | 101.8, 101.4, 103.2 |

## Conclusions

**Three indexes are kept.** For queries that select a small part of the table (one customer, one week, one product), each index replaces a full scan of about 8,000 pages with a read of 77 to 286 pages, and execution time falls from 31–38 ms to 0.2–3.4 ms. These are the access patterns of dashboard drill-downs and ad hoc investigation.

**The index on `invoice_no` was removed.** It was part of the first version of the schema, on the reasoning that orders are grouped by invoice. The measurement showed an identical plan and identical page count with and without it: aggregating every invoice has to read every row, so the planner correctly prefers a sequential scan. The index cost 4 MB and write overhead for no benefit, so it was dropped from `sql/schema/03_indexes.sql`.

**Whole-table analyses do not benefit from these indexes, and are not expected to.** Most queries in `sql/analysis/` aggregate the entire fact table. They run as sequential scans in roughly 100 to 130 ms at this size, which needs no tuning.

**`idx_fact_sales_customer_id` is partial** (`WHERE customer_id IS NOT NULL`). A quarter of fact rows have no customer and no query looks them up by a null key, so excluding them makes the index smaller (2.8 MB against 3.7 MB for the comparable full indexes).

## Limits of these measurements

- One machine, one dataset size, default PostgreSQL settings. Absolute times will differ elsewhere; the plan shapes and page counts are the transferable part.
- At 62 MB the whole table fits in memory. On a table that does not, the gap between an index scan and a sequential scan would be larger, and the whole-table queries would need a different approach, such as partitioning by month or pre-aggregated summary tables.
- The load is a full refresh, so index maintenance cost during loading was not measured separately.
