from __future__ import annotations

from dataclasses import dataclass


RISK_LEVEL_FACTORS = {
    "low": 0.02,
    "medium": 0.05,
    "high": 0.1,
}


@dataclass
class EstimateResult:
    direct_cost: float
    suggested_price: float
    gross_profit: float
    gross_margin_pct: float
    risk_buffer_cost: float
    warranty_buffer_cost: float



def _round2(value: float) -> float:
    return round(float(value), 2)



def compute_buffers(
    material_cost: float,
    labor_cost: float,
    travel_cost: float,
    risk_level: str,
    warranty_months: int,
) -> tuple[float, float]:
    base_cost = max(material_cost, 0.0) + max(labor_cost, 0.0) + max(travel_cost, 0.0)
    factor = RISK_LEVEL_FACTORS.get((risk_level or "medium").lower(), RISK_LEVEL_FACTORS["medium"])
    risk_buffer_cost = base_cost * factor

    # Warranty buffer starts at 0.25% per month and caps at 8% of base cost.
    warranty_rate = min(max(warranty_months, 0) * 0.0025, 0.08)
    warranty_buffer_cost = base_cost * warranty_rate

    return _round2(risk_buffer_cost), _round2(warranty_buffer_cost)



def estimate_price(
    material_cost: float,
    labor_cost: float,
    travel_cost: float,
    risk_level: str,
    warranty_months: int,
    target_margin_pct: float,
) -> EstimateResult:
    target_margin = max(min(float(target_margin_pct), 90.0), 5.0)

    risk_buffer_cost, warranty_buffer_cost = compute_buffers(
        material_cost=material_cost,
        labor_cost=labor_cost,
        travel_cost=travel_cost,
        risk_level=risk_level,
        warranty_months=warranty_months,
    )

    direct_cost = _round2(
        max(material_cost, 0.0)
        + max(labor_cost, 0.0)
        + max(travel_cost, 0.0)
        + risk_buffer_cost
        + warranty_buffer_cost
    )

    denominator = max(1.0 - (target_margin / 100.0), 0.05)
    suggested_price = _round2(direct_cost / denominator)
    gross_profit = _round2(suggested_price - direct_cost)
    gross_margin_pct = _round2((gross_profit / suggested_price) * 100.0 if suggested_price else 0.0)

    return EstimateResult(
        direct_cost=direct_cost,
        suggested_price=suggested_price,
        gross_profit=gross_profit,
        gross_margin_pct=gross_margin_pct,
        risk_buffer_cost=risk_buffer_cost,
        warranty_buffer_cost=warranty_buffer_cost,
    )



def evaluate_margin(final_price: float, direct_cost: float) -> tuple[float, float]:
    final_price = max(float(final_price), 0.0)
    direct_cost = max(float(direct_cost), 0.0)
    gross_profit = _round2(final_price - direct_cost)
    gross_margin_pct = _round2((gross_profit / final_price) * 100.0 if final_price else 0.0)
    return gross_profit, gross_margin_pct
