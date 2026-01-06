# medusa/webapp.py
from __future__ import annotations

import uuid
import random
from typing import Dict, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from medusa.config import TOTAL_TURNS, VIBE_MIN, VIBE_MAX, VIBE_START, CAPACITY_START, MALE_START, QUEER_START, NORMIE_START
from medusa.models import GameState, ClubState, SongCard, TurnResult
from medusa.generation import gen_base_song, deal_hand
from medusa.scoring import score_choice
from medusa.simulation import update_club

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory sessions (POC). Later: Redis/db or signed cookies.
SESSIONS: Dict[str, GameState] = {}


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def new_game(seed: Optional[int] = None) -> GameState:
    rng = random.Random(seed)
    active = gen_base_song(rng)
    club = ClubState(
        capacity=CAPACITY_START,
        male=MALE_START,
        queer=QUEER_START,
        normie=NORMIE_START,
    )
    state = GameState(
        rng_seed=seed,
        turn=0,
        score=0,
        vibe=VIBE_START,
        club=club,
        active_song=active,
    )
    state.hand = deal_hand(rng, state.active_song)
    return state


def get_rng(state: GameState) -> random.Random:
    # Deterministic per session if seed provided; otherwise stable randomness per run.
    return random.Random(state.rng_seed) if state.rng_seed is not None else random.Random()


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    # create a session and redirect to it
    sid = str(uuid.uuid4())
    SESSIONS[sid] = new_game(seed=None)
    return RedirectResponse(url=f"/game/{sid}", status_code=303)


@app.get("/game/{sid}", response_class=HTMLResponse)
def game_view(request: Request, sid: str):
    state = SESSIONS.get(sid)
    if not state:
        return RedirectResponse(url="/", status_code=303)

    if state.turn >= TOTAL_TURNS:
        return templates.TemplateResponse(
            "end.html",
            {
                "request": request,
                "sid": sid,
                "score": state.score,
                "turns": TOTAL_TURNS,
                "avg_vibe": (sum(tr.vibe_after for tr in state.history) / len(state.history)) if state.history else state.vibe,
                "peak_capacity": max([tr.capacity_after for tr in state.history], default=state.club.capacity),
            },
        )

    last_turn = state.history[-1] if state.history else None
    previous_song = last_turn.prev_active if last_turn else None

    return templates.TemplateResponse(
        "game.html",
        {
            "request": request,
            "sid": sid,
            "turn": state.turn,
            "turns": TOTAL_TURNS,
            "score": state.score,
            "vibe": state.vibe,
            "club": state.club,
            "active": state.active_song,
            "hand": state.hand,
            "last_reaction": state.last_reaction,
            "last_turn": last_turn,
            "previous": previous_song,
        },
    )


@app.post("/game/{sid}/play")
def play_card(sid: str, choice: int = Form(...)):
    state = SESSIONS.get(sid)
    if not state:
        return RedirectResponse(url="/", status_code=303)

    if state.turn >= TOTAL_TURNS:
        return RedirectResponse(url=f"/game/{sid}", status_code=303)

    # Validate choice (1..8)
    idx = int(choice) - 1
    if idx < 0 or idx >= len(state.hand):
        return RedirectResponse(url=f"/game/{sid}", status_code=303)

    # Use a per-session RNG stream:
    # POC: derive from (seed, turn) so it’s stable-ish.
    # If no seed, still okay.
    seed = state.rng_seed if state.rng_seed is not None else random.randrange(
        1_000_000_000)
    rng = random.Random(seed + state.turn * 10007)

    chosen = state.hand[idx]
    vibe_before = state.vibe
    cap_before = state.club.capacity

    points, vibe_delta, reaction, diag = score_choice(
        rng=rng,
        turn_index=state.turn,
        score_total=state.score,
        vibe=state.vibe,
        club=state.club,
        active_song=state.active_song,
        chosen=chosen,
        history=state.history,
    )

    vibe_after = clamp(state.vibe + vibe_delta, VIBE_MIN, VIBE_MAX)

    new_club, sim_diag = update_club(
        rng=rng,
        club=state.club,
        vibe_before=vibe_before,
        vibe_after=vibe_after,
        diagnostics=diag,
    )

    # Record history
    tr = TurnResult(
        turn_index=state.turn,
        chosen_index=idx,
        chosen_card=chosen,
        prev_active=state.active_song,
        points_gained=points,
        score_total=state.score + points,
        vibe_before=vibe_before,
        vibe_after=vibe_after,
        capacity_before=cap_before,
        capacity_after=new_club.capacity,
        diagnostics={**diag, **sim_diag},
        reaction=reaction,
    )

    state.history.append(tr)
    sign = "+" if points >= 0 else ""
    vsign = "+" if vibe_delta >= 0 else ""
    state.last_reaction = f"{sign}{points} pts • {vsign}{vibe_delta:.0f} vibe — {reaction}"

    # Apply state updates
    state.score += points
    state.vibe = vibe_after
    state.club = new_club
    state.active_song = chosen
    state.turn += 1

    # Deal next hand
    state.hand = deal_hand(rng, state.active_song)

    return RedirectResponse(url=f"/game/{sid}", status_code=303)
