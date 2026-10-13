from __future__ import annotations

import pandas as pd

DEFAULT_COGS_RATIOS = (0.50, 0.60, 0.70)


def margin_scenarios(
    gross_revenue: float, return_value: float, cogs_ratios: tuple[float, ...] = DEFAULT_COGS_RATIOS
) -> pd.DataFrame:
    """Illustrative gross margin under assumed cost-of-goods ratios.

    The source data contains no cost information. These figures are scenarios that show how
    far revenue can diverge from profit; they are not measured profitability.
    """
    for ratio in cogs_ratios:
        if not 0 <= ratio <= 1:
            raise ValueError(f"COGS ratio must be between 0 and 1, got {ratio}")
    net_revenue = gross_revenue - return_value
    rows = [
        {
            "assumed_cogs_ratio": ratio,
            "gross_revenue": gross_revenue,
            "return_value": return_value,
            "net_revenue": net_revenue,
            "assumed_cogs": net_revenue * ratio,
            "assumed_gross_margin": net_revenue * (1 - ratio),
            "assumed_margin_on_gross_revenue": (
                net_revenue * (1 - ratio) / gross_revenue if gross_revenue else float("nan")
            ),
        }
        for ratio in cogs_ratios
    ]
    return pd.DataFrame(rows)
