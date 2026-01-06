# medusa/simulation.py
from __future__ import annotations

import random
from typing import Dict, Tuple

from medusa.config import (
    CHURN_BASE,
    FILL_BASE,
    VIBE_FILL_BOOST,
    VIBE_CHURN_PENALTY,
    VIBE_MIN,
    VIBE_MAX,
)
from medusa.models import ClubState


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def vibe_to_01(vibe: float) -> float:
    span = VIBE_MAX - VIBE_MIN
    if span <= 0:
        return 0.5
    return clamp((vibe - VIBE_MIN) / span, 0.0, 1.0)


def update_club(
    *,
    rng: random.Random,
    club: ClubState,
    vibe_before: float,
    vibe_after: float,
    diagnostics: Dict[str, float],
) -> Tuple[ClubState, Dict[str, float]]:
    """
    Harder simulation:
      - capacity responds more violently to vibe + trainwreck
      - demographic splits drift faster (bigger random walk), especially on low vibe
    """
    cap_before = club.capacity
    did_trainwreck = diagnostics.get("did_trainwreck", 0.0) >= 0.5

    v01 = vibe_to_01(vibe_after)

    # Capacity: harsher churn at low vibe, harsher refill requirement
    churn = CHURN_BASE + (1.0 - v01) * (VIBE_CHURN_PENALTY * 1.35)
    fill = FILL_BASE + v01 * (VIBE_FILL_BOOST * 0.95)

    if did_trainwreck:
        churn += 0.14
        fill *= 0.45

    cap_after = cap_before
    cap_after -= cap_after * churn
    cap_after += (1.0 - cap_after) * fill
    cap_after = clamp(cap_after, 0.0, 1.0)

    # Demographics diverge faster:
    # - larger noise
    # - more turbulence when vibe is low or trainwreck
    turbulence = (1.0 - v01) * 0.22 + (0.18 if did_trainwreck else 0.0)

    def drift(value: float) -> float:
        # random walk with reflective bounds
        step = rng.uniform(-0.06, 0.06) * (0.55 + turbulence)
        return clamp(value + step, 0.02, 0.98)

    male_before = club.male
    queer_before = club.queer
    normie_before = club.normie

    male_after = drift(male_before)
    queer_after = drift(queer_before)
    normie_after = drift(normie_before)

    # Extra “room turnover” effect when capacity changes a lot
    cap_delta_abs = abs(cap_after - cap_before)
    if cap_delta_abs > 0.04:
        boost = min(0.12, cap_delta_abs * 1.5)
        male_after = clamp(male_after + rng.uniform(-boost, boost), 0.02, 0.98)
        queer_after = clamp(
            queer_after + rng.uniform(-boost, boost), 0.02, 0.98)
        normie_after = clamp(
            normie_after + rng.uniform(-boost, boost), 0.02, 0.98)

    new_club = ClubState(
        capacity=cap_after,
        male=male_after,
        queer=queer_after,
        normie=normie_after,
    )

    sim_diag = {
        "capacity_before": cap_before,
        "capacity_after": cap_after,
        "capacity_delta": cap_after - cap_before,
        "male_before": male_before,
        "male_after": male_after,
        "male_delta": male_after - male_before,
        "queer_before": queer_before,
        "queer_after": queer_after,
        "queer_delta": queer_after - queer_before,
        "normie_before": normie_before,
        "normie_after": normie_after,
        "normie_delta": normie_after - normie_before,
        "churn": churn,
        "fill": fill,
        "turbulence": turbulence,
    }

    return new_club, sim_diag
