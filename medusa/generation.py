# medusa/generation.py
from __future__ import annotations

import random
from typing import List, Tuple

from medusa.config import (
    BPM_MIN,
    BPM_MAX,
    HAND_SIZE,
    SIMILAR_CARDS,
    DIFFERENT_CARDS,
)
from medusa.models import SongCard
from medusa.genre import GENRES, genre_index, genre_distance, get_genre_def


def clamp_int(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x


def sample_trunc_normal_int(
    rng: random.Random,
    mean: float,
    std: float,
    lo: int,
    hi: int,
) -> int:
    """
    Sample an int from a truncated normal distribution using rejection sampling.
    For our small stds this is fast in practice.
    """
    if std <= 0:
        return clamp_int(int(round(mean)), lo, hi)

    for _ in range(30):
        x = rng.gauss(mean, std)
        if lo <= x <= hi:
            return int(round(x))
    # Fallback if rejection fails
    return clamp_int(int(round(mean)), lo, hi)


def random_genre(rng: random.Random) -> str:
    return rng.choice(GENRES)


def _neighbor_genres(genre: str) -> Tuple[str, str]:
    """Return the two adjacent genres on the ring."""
    i = genre_index(genre)
    n = len(GENRES)
    return (GENRES[(i - 1) % n], GENRES[(i + 1) % n])


def _far_genres(active_genre: str, min_dist: int = 3) -> List[str]:
    """Genres at least `min_dist` away on the ring."""
    return [g for g in GENRES if genre_distance(active_genre, g) >= min_dist]


def _genre_bpm_bounds(genre: str) -> tuple[int, int]:
    gd = get_genre_def(genre)
    lo = int(gd.bpm.min) if gd.bpm.min is not None else BPM_MIN
    hi = int(gd.bpm.max) if gd.bpm.max is not None else BPM_MAX
    lo = max(BPM_MIN, lo)
    hi = min(BPM_MAX, hi)
    if lo >= hi:
        lo, hi = BPM_MIN, BPM_MAX
    return lo, hi


def gen_base_song(rng: random.Random) -> SongCard:
    """A random song whose BPM is shaped by the genre distribution."""
    genre = random_genre(rng)
    gd = get_genre_def(genre)
    lo, hi = _genre_bpm_bounds(genre)
    bpm = sample_trunc_normal_int(rng, gd.bpm.mean, gd.bpm.std, lo, hi)
    return SongCard(bpm=bpm, genre=genre)


def gen_similar_song(rng: random.Random, active: SongCard) -> SongCard:
    """
    Similar:
      - genre: same most of the time, otherwise adjacent on the ring
      - bpm: sampled from the *target genre* distribution, nudged toward active bpm
    """
    if rng.random() < 0.75:
        genre = active.genre
    else:
        left, right = _neighbor_genres(active.genre)
        genre = rng.choice([left, right])

    gd = get_genre_def(genre)
    lo, hi = _genre_bpm_bounds(genre)

    # For "similar", blend current bpm with genre mean (leans toward current song)
    mean = 0.65 * active.bpm + 0.35 * gd.bpm.mean
    std = max(3.0, gd.bpm.std * 0.70)

    bpm = sample_trunc_normal_int(rng, mean, std, lo, hi)
    return SongCard(bpm=bpm, genre=genre)


def gen_different_song(rng: random.Random, active: SongCard) -> SongCard:
    """
    Different:
      - genre: at least a few steps away (POC)
      - bpm: sampled from target genre distribution, leaning toward genre mean
    """
    candidates = _far_genres(active.genre, min_dist=3)
    genre = rng.choice(candidates) if candidates else random_genre(rng)

    gd = get_genre_def(genre)
    lo, hi = _genre_bpm_bounds(genre)

    # For "different", lean harder toward genre mean
    mean = 0.25 * active.bpm + 0.75 * gd.bpm.mean
    std = max(4.0, gd.bpm.std)

    bpm = sample_trunc_normal_int(rng, mean, std, lo, hi)

    # Occasional wildcard BPM to create true "risk cards"
    if rng.random() < 0.12:
        bpm = sample_trunc_normal_int(
            rng, gd.bpm.mean, gd.bpm.std * 1.25, lo, hi)

    return SongCard(bpm=bpm, genre=genre)


def deal_hand(rng: random.Random, active: SongCard) -> List[SongCard]:
    """
    Deal HAND_SIZE cards:
      - SIMILAR_CARDS similar to the active song
      - DIFFERENT_CARDS different from the active song
    Then shuffle.
    """
    if SIMILAR_CARDS + DIFFERENT_CARDS != HAND_SIZE:
        raise ValueError(
            "SIMILAR_CARDS + DIFFERENT_CARDS must equal HAND_SIZE")

    hand: List[SongCard] = []
    for _ in range(SIMILAR_CARDS):
        hand.append(gen_similar_song(rng, active))
    for _ in range(DIFFERENT_CARDS):
        hand.append(gen_different_song(rng, active))

    rng.shuffle(hand)
    return hand
