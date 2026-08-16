from __future__ import annotations

from typing import Literal

ImpactDirection = Literal["higher_better", "lower_better"]
ImpactStatus = Literal["pending", "target_met", "improved_not_met", "no_change", "regressed"]


def evaluate_impact(
    *,
    direction: ImpactDirection,
    baseline_value: float,
    target_value: float,
    outcome_value: float | None,
) -> dict[str, float | str | None]:
    """Evaluate only the arithmetic effect of a recorded target.

    This function does not define a pedagogical threshold or claim that a target is
    officially approved. Any educational standard must be supplied with its source
    by the caller and stored separately.
    """
    baseline = float(baseline_value)
    target = float(target_value)
    outcome = float(outcome_value) if outcome_value is not None else None
    if outcome is None:
        return {
            "impactStatus": "pending",
            "impactDelta": None,
            "improvementValue": None,
            "targetGap": None,
        }

    delta = outcome - baseline
    improvement = delta if direction == "higher_better" else -delta
    target_met = outcome >= target if direction == "higher_better" else outcome <= target
    if target_met:
        status: ImpactStatus = "target_met"
    elif improvement > 0:
        status = "improved_not_met"
    elif improvement == 0:
        status = "no_change"
    else:
        status = "regressed"

    raw_gap = target - outcome if direction == "higher_better" else outcome - target
    target_gap = max(0.0, raw_gap)
    return {
        "impactStatus": status,
        "impactDelta": round(delta, 6),
        "improvementValue": round(improvement, 6),
        "targetGap": round(target_gap, 6),
    }
