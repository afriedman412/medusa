# djrogue/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SongCard:
    """A playable (or active) song."""
    bpm: int
    genre: str


@dataclass
class ClubState:
    """
    All ratios are 0..1 and represent the LEFT label share:
      male = 0.60 -> 60% male / 40% female
      queer = 0.40 -> 40% queer / 60% straight
      normie = 0.55 -> 55% normie / 45% cool
    capacity is 0..1 (% full).
    """
    capacity: float

    male: float
    queer: float
    normie: float


@dataclass
class TurnResult:
    """What happened after playing one card."""
    turn_index: int

    chosen_index: int          # 0..7 (index into hand)
    chosen_card: SongCard
    prev_active: SongCard

    points_gained: int
    score_total: int

    vibe_before: float
    vibe_after: float

    capacity_before: float
    capacity_after: float

    # Useful for later debugging/balancing and for a future "history" view.
    diagnostics: Dict[str, float] = field(default_factory=dict)
    reaction: str = ""


@dataclass
class GameState:
    """
    The current game state. Keep this as a 'data bag' — logic lives elsewhere.
    """
    rng_seed: Optional[int]

    turn: int
    score: int
    vibe: float

    club: ClubState
    active_song: SongCard

    # Most recent dealt hand (set each turn by generation)
    hand: List[SongCard] = field(default_factory=list)

    # Full turn-by-turn history
    history: List[TurnResult] = field(default_factory=list)

    # Optional: last message for UI flavor
    last_reaction: str = ""
