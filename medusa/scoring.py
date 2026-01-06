# medusa/scoring.py
from __future__ import annotations

import random
from typing import Dict, List, Tuple

from medusa.config import (
    BASE_POINTS,
    VARIETY_WINDOW,
    SAFE_SIMILARITY_CAP,
    VIBE_MIN,
    VIBE_MAX,
)
from medusa.models import ClubState, SongCard, TurnResult
from medusa.genre import song_similarity, get_genre_def


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def vibe_to_01(vibe: float) -> float:
    span = VIBE_MAX - VIBE_MIN
    if span <= 0:
        return 0.5
    return clamp((vibe - VIBE_MIN) / span, 0.0, 1.0)


def sample_appeal_for_room(rng: random.Random, club: ClubState, genre: str) -> float:
    gd = get_genre_def(genre)

    a_male = clamp(rng.gauss(gd.appeal_male.mean,
                   gd.appeal_male.std), 0.0, 1.0)
    a_queer = clamp(rng.gauss(gd.appeal_queer.mean,
                    gd.appeal_queer.std), 0.0, 1.0)
    a_normie = clamp(rng.gauss(gd.appeal_normie.mean,
                     gd.appeal_normie.std), 0.0, 1.0)

    male_part = club.male * a_male + (1.0 - club.male) * (1.0 - a_male)
    queer_part = club.queer * a_queer + (1.0 - club.queer) * (1.0 - a_queer)
    normie_part = club.normie * a_normie + \
        (1.0 - club.normie) * (1.0 - a_normie)

    blended = (male_part + queer_part + normie_part) / 3.0

    # keep it soft and non-solvable
    return 0.25 + 0.75 * blended  # ~[0.25..1.0]


def variety_score(history: List[TurnResult], chosen: SongCard) -> float:
    recent = history[-VARIETY_WINDOW:] if VARIETY_WINDOW > 0 else history
    genres = [tr.chosen_card.genre for tr in recent] + [chosen.genre]
    if not genres:
        return 0.5
    unique = len(set(genres))
    return unique / len(genres)


def repetition_penalty(history: List[TurnResult], chosen: SongCard) -> Dict[str, float]:
    """
    HARD MODE: punish same-genre & close-BPM repetition heavily.
    Goal: three similar rap tracks in a row should crater points (e.g. ~50 from 100).

    Returns dict with:
      rep_mult in (0..1]
      rep_hits: count of "samey" matches in recent window
    """
    window = history[-3:]  # last 3 plays is enough to feel it
    hits = 0
    mult = 1.0

    for tr in reversed(window):
        prev = tr.chosen_card
        same_genre = (prev.genre == chosen.genre)
        bpm_close = abs(prev.bpm - chosen.bpm) <= 8

        # "samey" = same genre + close bpm
        if same_genre and bpm_close:
            hits += 1
            mult *= 0.72  # stacks hard: 1 hit ~0.72, 2 hits ~0.52, 3 hits ~0.37

        # also punish ultra-high similarity regardless of genre name
        sim = song_similarity(prev.genre, prev.bpm, chosen.genre, chosen.bpm)
        if sim >= 0.88:
            mult *= 0.88

    # floor so it’s not literally zero
    mult = clamp(mult, 0.30, 1.0)
    return {"rep_mult": mult, "rep_hits": float(hits)}


def score_choice(
    *,
    rng: random.Random,
    turn_index: int,
    score_total: int,
    vibe: float,  # -100..100
    club: ClubState,
    active_song: SongCard,
    chosen: SongCard,
    history: List[TurnResult],
) -> Tuple[int, float, str, Dict[str, float]]:
    vibe01 = vibe_to_01(vibe)

    similarity = song_similarity(
        active_song.genre, active_song.bpm,
        chosen.genre, chosen.bpm,
    )
    risk = 1.0 - similarity

    appeal = sample_appeal_for_room(rng, club, chosen.genre)
    variety = variety_score(history, chosen)

    rep = repetition_penalty(history, chosen)
    rep_mult = rep["rep_mult"]

    # SAFE CAP IS STRONGER in hard mode
    safe_penalty = 1.0
    if similarity >= SAFE_SIMILARITY_CAP:
        safe_penalty = 0.70

    # Make low variety actively bad (not just “less good”)
    # variety in [~0.25..1.0]; map to [0.55..1.15]
    variety_mult = 0.55 + 0.60 * variety

    # Vibe multiplier: harder curve (low vibe feels terrible)
    vibe_mult = 0.35 + 1.15 * vibe01  # 0.35..1.50

    # Appeal has bigger effect
    appeal_mult = 0.55 + 0.95 * appeal  # 0.79..1.45

    raw_points = BASE_POINTS * vibe_mult * appeal_mult * \
        variety_mult * safe_penalty * rep_mult

    # Stronger trainwreck:
    # - higher threshold
    # - higher chance cap
    trainwreck_threshold = 0.45
    trainwreck_chance = 0.0
    if similarity < trainwreck_threshold:
        # risk drives it up; low vibe drives it up
        trainwreck_chance = clamp(
            (risk * 1.05) + ((1.0 - vibe01) * 0.35), 0.0, 0.88)

    did_trainwreck = (rng.random() < trainwreck_chance)

    # Vibe delta in vibe points
    vibe_delta = 0.0
    vibe_delta += (appeal - 0.65) * 22.0
    vibe_delta += (variety - 0.55) * 12.0
    vibe_delta -= (risk) * 12.0
    vibe_delta -= (1.0 - rep_mult) * 18.0  # repeating drains vibe

    reaction = ""

    if did_trainwreck:
        # Trainwreck should feel brutal
        raw_points *= 0.12
        vibe_delta -= (26.0 + 28.0 * risk)
        reaction = "TRAINWRECK! You lose the room — people bail fast."
    else:
        # “pop-off” chance exists but is rarer
        surprise_chance = clamp(
            (appeal * 0.18) + (variety * 0.14) - (similarity * 0.10), 0.0, 0.14)
        if rng.random() < surprise_chance and similarity < 0.75:
            raw_points *= 1.12
            vibe_delta += 6.0
            reaction = "Switch-up lands — hands go up."

    if not reaction:
        if rep_mult < 0.65:
            reaction = "Same lane too long — the room gets restless."
        elif appeal > 0.85 and similarity > 0.55:
            reaction = "Locked in. The room nods in unison."
        elif appeal > 0.85 and similarity <= 0.55:
            reaction = "Bold choice, but it hits. The floor heats up."
        elif appeal <= 0.60 and similarity > 0.70:
            reaction = "Safe, but the room looks bored."
        elif appeal <= 0.60 and similarity <= 0.55:
            reaction = "Hmm… people start drifting."
        else:
            reaction = "Solid. The vibe holds."

    # Still non-negative for now (you wanted to think about negatives later)
    points_gained = max(0, int(round(raw_points)))

    diagnostics = {
        "vibe01": vibe01,
        "similarity": similarity,
        "risk": risk,
        "appeal": appeal,
        "variety": variety,
        "safe_penalty": safe_penalty,
        "rep_mult": rep_mult,
        "rep_hits": rep["rep_hits"],
        "trainwreck_threshold": trainwreck_threshold,
        "trainwreck_chance": trainwreck_chance,
        "did_trainwreck": 1.0 if did_trainwreck else 0.0,
        "vibe_mult": vibe_mult,
        "appeal_mult": appeal_mult,
        "variety_mult": variety_mult,
    }
    return points_gained, vibe_delta, reaction, diagnostics
