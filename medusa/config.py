# djrogue/config.py

# Time structure
TURNS_PER_HOUR = 15
HOURS = 6
TOTAL_TURNS = TURNS_PER_HOUR * HOURS

# Hand/deck
HAND_SIZE = 8
SIMILAR_CARDS = 5
DIFFERENT_CARDS = HAND_SIZE - SIMILAR_CARDS

# BPM bounds (POC)
BPM_MIN = 85
BPM_MAX = 175

# Vibe
VIBE_MIN = -100.0
VIBE_MAX = 100.0
VIBE_START = 0.0

# Club state
CAPACITY_START = 0.01  # % full at start (0..1)

# Starting demographics (ratios are 0..1; e.g. male=0.6 means 60% male / 40% female)
MALE_START = 0.55
QUEER_START = 0.45
NORMIE_START = 0.55

# Similar/different generation tuning
SIMILAR_BPM_DELTA = 10        # similar cards keep bpm within +/- this
DIFFERENT_BPM_DELTA = 35      # different cards can drift wider than similar

# Scoring tuning
BASE_POINTS = 100             # scale
SAFE_SIMILARITY_CAP = 0.80    # high similarity limits max reward a bit
VARIETY_WINDOW = 8            # how many recent songs count for variety bonus

# Capacity & churn tuning
CHURN_BASE = 0.03             # normal per-turn churn (fraction of crowd)
FILL_BASE = 0.02              # normal refill rate if vibe is decent
VIBE_FILL_BOOST = 0.06        # additional refill at high vibe
VIBE_CHURN_PENALTY = 0.08     # additional churn at low vibe

# UI
VIBE_BAR_WIDTH = 28
