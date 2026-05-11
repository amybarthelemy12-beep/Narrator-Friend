"""Production cost estimates: narrator fee, post-production, optional proofing.

All rates are per *finished* hour (PFH) — the standard ACX/audiobook unit. The
finished-hour count comes straight from the recording-time estimate:

    finished_hours      = total_words / words_per_hour
    narrator_cost       = finished_hours * narrator_rate
    post_production_cost = finished_hours * editing_rate
    proofing_cost       = finished_hours * proofing_rate   (optional)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# ACX-scale narrator rate presets, per finished hour.
EXPERIENCE_RATES: dict[str, float] = {
    "new": 150.0,
    "mid": 275.0,
    "experienced": 400.0,
}
DEFAULT_EXPERIENCE = "mid"

# Typical ranges per finished hour:
#   narrator:           $150-400 (ACX scale)
#   editing/mastering:  $50-100
#   proofing (opt):     $25-50
DEFAULT_NARRATOR_RATE = EXPERIENCE_RATES[DEFAULT_EXPERIENCE]
DEFAULT_EDITING_RATE = 75.0
DEFAULT_PROOFING_RATE = 37.5


@dataclass
class CostEstimate:
    finished_hours: float
    narrator_rate: float
    editing_rate: float
    proofing_rate: float  # 0 when proofing is disabled
    narrator_cost: float
    editing_cost: float
    proofing_cost: float
    total_cost: float

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, float):
                d[k] = round(v, 2)
        return d


def finished_hours(total_words: int, words_per_hour: int) -> float:
    if words_per_hour <= 0 or total_words <= 0:
        return 0.0
    return total_words / words_per_hour


def estimate_costs(
    total_words: int,
    words_per_hour: int,
    narrator_rate: float = DEFAULT_NARRATOR_RATE,
    editing_rate: float = DEFAULT_EDITING_RATE,
    proofing_rate: float = 0.0,
) -> CostEstimate:
    hours = finished_hours(total_words, words_per_hour)
    nr = max(0.0, float(narrator_rate))
    er = max(0.0, float(editing_rate))
    pr = max(0.0, float(proofing_rate))
    narrator_cost = hours * nr
    editing_cost = hours * er
    proofing_cost = hours * pr
    return CostEstimate(
        finished_hours=hours,
        narrator_rate=nr,
        editing_rate=er,
        proofing_rate=pr,
        narrator_cost=narrator_cost,
        editing_cost=editing_cost,
        proofing_cost=proofing_cost,
        total_cost=narrator_cost + editing_cost + proofing_cost,
    )
