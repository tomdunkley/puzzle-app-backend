import random
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.db import cryptic_clues_table
from app.services.user_service import is_developer

_DICT_PATH = Path(__file__).parent.parent / "data" / "dictionary.txt"
_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

_WORD_SQUARE_DEADLINE_SECS = 4.0


class NotADeveloperError(Exception):
    pass


@lru_cache(maxsize=1)
def _words_by_length() -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for w in _DICT_PATH.read_text().splitlines():
        w = w.strip().upper()
        if w.isalpha() and 3 <= len(w) <= 6:
            result.setdefault(len(w), []).append(w)
    return result


@lru_cache(maxsize=6)
def _prefix_index(length: int) -> frozenset[str]:
    """All valid prefixes (including full words) for words of the given length."""
    words = _words_by_length().get(length, [])
    prefixes: set[str] = set()
    for w in words:
        for i in range(1, len(w) + 1):
            prefixes.add(w[:i])
    return frozenset(prefixes)


def list_clues(user_id: str) -> list[dict]:
    if not is_developer(user_id):
        raise NotADeveloperError()
    result = cryptic_clues_table.scan()
    items = result.get("Items", [])
    while "LastEvaluatedKey" in result:
        result = cryptic_clues_table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
        items.extend(result.get("Items", []))
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def update_clue(user_id: str, clue_id: str, solution: str, clue: str) -> None:
    if not is_developer(user_id):
        raise NotADeveloperError()
    cryptic_clues_table.update_item(
        Key={"clue_id": clue_id},
        UpdateExpression="SET solution = :s, clue = :c",
        ExpressionAttributeValues={":s": solution, ":c": clue},
    )


def delete_clue(user_id: str, clue_id: str) -> None:
    if not is_developer(user_id):
        raise NotADeveloperError()
    cryptic_clues_table.delete_item(Key={"clue_id": clue_id})


def submit_clue(user_id: str, solution: str, clue: str) -> None:
    if not is_developer(user_id):
        raise NotADeveloperError()
    cryptic_clues_table.put_item(Item={
        "clue_id": str(uuid.uuid4()),
        "solution": solution,
        "clue": clue,
        "submitted_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def suggest_words(user_id: str) -> tuple[list[str], int]:
    if not is_developer(user_id):
        raise NotADeveloperError()

    rng = random.Random()
    deadline = time.monotonic() + _WORD_SQUARE_DEADLINE_SECS

    sizes = [4, 5]
    rng.shuffle(sizes)
    for size in sizes:
        words = _build_word_square(size, rng, deadline)
        if words:
            return words, size

    return [], 0


def _build_word_square(
    size: int, rng: random.Random, deadline: float
) -> list[str] | None:
    wbl = _words_by_length()
    all_words = wbl.get(size, [])
    if not all_words:
        return None

    words_set = set(all_words)
    prefixes = _prefix_index(size)
    shuffled_all = list(all_words)
    rng.shuffle(shuffled_all)

    grid: list[str] = []

    def valid_chars_per_col(row_idx: int) -> list[set[str]]:
        # For each column j, the column prefix is grid[0][j]...grid[row_idx-1][j].
        # A character c is valid at column j if col_prefix + c is a valid prefix.
        result = []
        for j in range(size):
            col_prefix = "".join(grid[i][j] for i in range(row_idx))
            valid = {c for c in _ALPHABET if col_prefix + c in prefixes}
            result.append(valid)
        return result

    def candidates(row_idx: int) -> list[str]:
        valid_at = valid_chars_per_col(row_idx)
        # Row 0: use pre-shuffled list; other rows: filter the full list
        source = shuffled_all if row_idx == 0 else all_words
        result = [w for w in source if all(w[j] in valid_at[j] for j in range(size))]
        if row_idx > 0:
            rng.shuffle(result)
        return result[:50]

    def backtrack(row: int) -> bool:
        if time.monotonic() > deadline:
            return False
        if row == size:
            # All column characters were already validated at each step
            return True
        for w in candidates(row):
            grid.append(w)
            if backtrack(row + 1):
                return True
            grid.pop()
        return False

    if not backtrack(0):
        return None

    # Return rows + any distinct column words
    result = list(grid)
    for j in range(size):
        col = "".join(grid[i][j] for i in range(size))
        if col not in result:
            result.append(col)
    return result
