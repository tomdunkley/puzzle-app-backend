from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db import puzzles_table
from app.services.boggle import find_all_words, generate_board
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


def _precompute_future_puzzles(today_date_iso: str, game: str, days_ahead: int = 5) -> None:
    """Pre-creates puzzle items for upcoming days so the board/numbers are already
    seeded when each day arrives. The all_words list for boggle is computed for the
    furthest-out day (days_ahead) so it will be cached by the time that day starts.
    """
    today = date.fromisoformat(today_date_iso)
    for offset in range(1, days_ahead + 1):
        future_date = (today + timedelta(days=offset)).isoformat()
        future_id = f"{game}_{future_date}"
        if puzzles_table.get_item(Key={"puzzle_id": future_id}).get("Item") is not None:
            continue
        if game == "numbers":
            round_ = generate_round(seed=future_id)
            puzzles_table.put_item(Item={
                "puzzle_id": future_id,
                "game": game,
                "date": future_date,
                "numbers": round_["numbers"],
                "target": round_["target"],
                "solution": round_["solution"],
                "duration_seconds": NUMBERS_DURATION_SECONDS,
            })
        else:
            board = generate_board(seed=future_id)
            item: dict = {
                "puzzle_id": future_id,
                "game": game,
                "date": future_date,
                "board": board,
                "duration_seconds": DEFAULT_DURATION_SECONDS,
            }
            if offset == days_ahead:
                # Pre-compute all_words for the furthest-out day so it's ready early.
                item["all_words"] = find_all_words(board)
            puzzles_table.put_item(Item=item)


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
        board = generate_board(seed=puzzle_id)
        puzzle = {
            "puzzle_id": puzzle_id,
            "game": game,
            "date": date_iso,
            "board": board,
            "duration_seconds": DEFAULT_DURATION_SECONDS,
            # Compute all_words eagerly at creation time so the first /all-words
            # request for this puzzle is instant rather than paying the DFS cost live.
            "all_words": find_all_words(board),
        }
    puzzles_table.put_item(Item=puzzle)
    _precompute_future_puzzles(date_iso, game)
    return puzzle


def get_puzzle_all_words(puzzle_id: str) -> list[dict] | None:
    """Returns all valid words for a boggle puzzle, computing and caching on first call."""
    puzzle = get_puzzle(puzzle_id)
    if puzzle is None or puzzle.get("game") != "boggle":
        return None
    if "all_words" in puzzle:
        return [{"word": str(e["word"]), "score": int(e["score"])} for e in puzzle["all_words"]]
    words = find_all_words(puzzle["board"])
    puzzles_table.update_item(
        Key={"puzzle_id": puzzle_id},
        UpdateExpression="SET all_words = :w",
        ExpressionAttributeValues={":w": words},
    )
    return words


def get_puzzle(puzzle_id: str) -> dict | None:
    response = puzzles_table.get_item(Key={"puzzle_id": puzzle_id})
    return response.get("Item")
