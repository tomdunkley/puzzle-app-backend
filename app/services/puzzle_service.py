from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db import puzzles_table
from app.services.boggle import generate_board
from app.services.numbers_game import generate_round

GAMES = [
    {
        "game": "boggle",
        "title": "Words",
        "description": "Find as many words as you can before time runs out.",
    },
    {
        "game": "numbers",
        "title": "Numbers",
        "description": "Combine six numbers to hit the target.",
    },
]

DEFAULT_DURATION_SECONDS = 90
NUMBERS_DURATION_SECONDS = 60


def list_games() -> list[dict]:
    return GAMES


def today_iso() -> str:
    # The "day" starts at 8am UK time (Europe/London handles BST/GMT automatically).
    # Before 8am London time, we're still serving "yesterday's" puzzles.
    london = ZoneInfo("Europe/London")
    now = datetime.now(london)
    if now.hour < 8:
        return (now.date() - timedelta(days=1)).isoformat()
    return now.date().isoformat()


def get_or_create_today_puzzle(game: str) -> dict:
    date_iso = today_iso()
    # Must stay URL-safe: this value is also used as a path parameter
    # (GET /v1/puzzles/{puzzle_id}, GET /v1/leaderboards/{puzzle_id}), so
    # characters with special meaning in URLs (#, /, ?, &) are off-limits.
    puzzle_id = f"{game}_{date_iso}"

    response = puzzles_table.get_item(Key={"puzzle_id": puzzle_id})
    existing = response.get("Item")
    if existing is not None:
        return existing

    if game == "numbers":
        round_ = generate_round(seed=puzzle_id)
        puzzle = {
            "puzzle_id": puzzle_id,
            "game": game,
            "date": date_iso,
            "numbers": round_["numbers"],
            "target": round_["target"],
            "solution": round_["solution"],
            "duration_seconds": NUMBERS_DURATION_SECONDS,
        }
    else:
        puzzle = {
            "puzzle_id": puzzle_id,
            "game": game,
            "date": date_iso,
            "board": generate_board(seed=puzzle_id),
            "duration_seconds": DEFAULT_DURATION_SECONDS,
        }
    puzzles_table.put_item(Item=puzzle)
    return puzzle


def get_puzzle(puzzle_id: str) -> dict | None:
    response = puzzles_table.get_item(Key={"puzzle_id": puzzle_id})
    return response.get("Item")
