# medusa/genre.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from medusa.config import BPM_MIN, BPM_MAX


@dataclass(frozen=True)
class Dist:
    mean: float
    std: float
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass(frozen=True)
class GenreDef:
    name: str
    bpm: Dist
    # These are *genre tendencies*, not hard rules.
    # Each is a distribution for how this genre tends to land with that dimension.
    appeal_male: Dist
    appeal_queer: Dist
    appeal_normie: Dist
    attributes: List[str]


def _default_genre(name: str) -> GenreDef:
    return GenreDef(
        name=name,
        bpm=Dist(mean=125, std=10, min=BPM_MIN, max=BPM_MAX),
        appeal_male=Dist(mean=0.5, std=0.12),
        appeal_queer=Dist(mean=0.5, std=0.12),
        appeal_normie=Dist(mean=0.5, std=0.12),
        attributes=[],
    )


def load_genres(path: str) -> Dict[str, GenreDef]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    out: Dict[str, GenreDef] = {}
    for name, g in raw.items():
        bpm = g.get("bpm", {})
        appeal = g.get("appeal", {})
        out[name] = GenreDef(
            name=name,
            bpm=Dist(
                mean=float(bpm.get("mean", 125)),
                std=float(bpm.get("std", 10)),
                min=float(bpm.get("min", BPM_MIN)) if bpm.get(
                    "min") is not None else None,
                max=float(bpm.get("max", BPM_MAX)) if bpm.get(
                    "max") is not None else None,
            ),
            appeal_male=Dist(
                mean=float(appeal.get("male", {}).get("mean", 0.5)),
                std=float(appeal.get("male", {}).get("std", 0.12)),
            ),
            appeal_queer=Dist(
                mean=float(appeal.get("queer", {}).get("mean", 0.5)),
                std=float(appeal.get("queer", {}).get("std", 0.12)),
            ),
            appeal_normie=Dist(
                mean=float(appeal.get("normie", {}).get("mean", 0.5)),
                std=float(appeal.get("normie", {}).get("std", 0.12)),
            ),
            attributes=list(g.get("attributes", [])),
        )
    return out


# --- Locate data file (relative to project root) ---
# This assumes repo structure:
#   medusa/ (package)
#   data/genres.json
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_GENRE_PATH = os.path.join(_REPO_ROOT, "data", "genres.json")

GENRE_DEFS: Dict[str, GenreDef]
try:
    GENRE_DEFS = load_genres(_GENRE_PATH)
except FileNotFoundError:
    GENRE_DEFS = {}

GENRES: List[str] = sorted(GENRE_DEFS.keys()) if GENRE_DEFS else [
    # fallback if JSON missing
    "house", "techno", "disco", "hiphop", "pop", "rnb", "garage", "dnb", "electro", "funk"
]


# --- Ring distance (keep for now; later swap for matrix/graph) ---
def genre_index(genre: str) -> int:
    try:
        return GENRES.index(genre)
    except ValueError as e:
        raise ValueError(f"Unknown genre: {genre}") from e


def genre_distance(a: str, b: str) -> int:
    ia = genre_index(a)
    ib = genre_index(b)
    n = len(GENRES)
    raw = abs(ia - ib)
    return min(raw, n - raw)


def genre_distance_norm(a: str, b: str) -> float:
    max_dist = max(1, len(GENRES) // 2)
    return genre_distance(a, b) / max_dist


def bpm_distance_norm(bpm_a: int, bpm_b: int) -> float:
    span = BPM_MAX - BPM_MIN
    return abs(bpm_a - bpm_b) / span


def song_similarity(
    genre_a: str,
    bpm_a: int,
    genre_b: str,
    bpm_b: int,
    *,
    genre_weight: float = 0.65,
    bpm_weight: float = 0.35,
) -> float:
    gd = genre_distance_norm(genre_a, genre_b)
    bd = bpm_distance_norm(bpm_a, bpm_b)
    dist = (genre_weight * gd) + (bpm_weight * bd)
    return 1.0 - min(dist, 1.0)


def get_genre_def(name: str) -> GenreDef:
    return GENRE_DEFS.get(name) or _default_genre(name)
