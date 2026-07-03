import random
from functools import lru_cache
from pathlib import Path

BOARD_SIZE = 5
MIN_WORD_LENGTH = 4

# Real "Big Boggle" (5x5, 25 dice) letter distribution. Source: community-compiled
# distribution widely used by digital Boggle implementations and solvers (Hasbro's
# own rules PDF doesn't print exact die faces) -- see BoardGameGeek "Letter
# Distribution | Big Boggle" thread. "Q" always appears as a single die face
# representing the "Qu" tile, per standard Boggle convention.
BIG_BOGGLE_DICE = [
    "AAAFRS", "AAEEEE", "AAFIRS", "ADENNN", "AEEEEM",
    "AEEGMU", "AEGMNN", "AFIRSY", "BJKQXZ", "CCNSTW",
    "CEIILT", "CEILPT", "CEIPST", "DDLNOR", "DHHLOR",
    "DHHNOT", "DHLNOR", "EIIITT", "EMOTTT", "ENSSSU",
    "FIPRSY", "GORRVW", "HIPRRY", "NOOTUW", "OOOTTU",
]

# Official Boggle scoring by word length, with words under MIN_WORD_LENGTH worth
# nothing (house rule requested: minimum word length of four).
_SCORE_BY_LENGTH = {4: 1, 5: 2, 6: 3, 7: 5}
_SCORE_FOR_LONG_WORDS = 11  # 8+ letters


def score_for_word_length(length: int) -> int:
    if length < MIN_WORD_LENGTH:
        return 0
    return _SCORE_BY_LENGTH.get(length, _SCORE_FOR_LONG_WORDS)


def generate_board(seed: str) -> list[str]:
    """Deterministic 5x5 board: same seed (e.g. today's date) always yields the same board."""
    rng = random.Random(seed)
    dice = list(BIG_BOGGLE_DICE)
    rng.shuffle(dice)
    board = []
    for die in dice:
        face = rng.choice(die)
        board.append("QU" if face == "Q" else face)
    return board


def _neighbors(index: int) -> list[int]:
    row, col = divmod(index, BOARD_SIZE)
    neighbors = []
    for d_row in (-1, 0, 1):
        for d_col in (-1, 0, 1):
            if d_row == 0 and d_col == 0:
                continue
            r, c = row + d_row, col + d_col
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                neighbors.append(r * BOARD_SIZE + c)
    return neighbors


_ADJACENCY = {i: _neighbors(i) for i in range(BOARD_SIZE * BOARD_SIZE)}


def can_form_word(board: list[str], word: str) -> bool:
    """True if `word` can be spelled by a path of adjacent, non-reused board cells."""
    target = word.upper()

    def dfs(index: int, visited: set[int], remaining: str) -> bool:
        cell = board[index]
        if not remaining.startswith(cell):
            return False
        remaining = remaining[len(cell):]
        if not remaining:
            return True
        visited.add(index)
        for neighbor in _ADJACENCY[index]:
            if neighbor not in visited and dfs(neighbor, visited, remaining):
                visited.remove(index)
                return True
        visited.remove(index)
        return False

    return any(dfs(i, set(), target) for i in range(len(board)) if target.startswith(board[i]))


@lru_cache(maxsize=1)
def _dictionary() -> frozenset[str]:
    path = Path(__file__).resolve().parent.parent / "data" / "dictionary.txt"
    with path.open(encoding="utf-8") as f:
        return frozenset(line.strip().upper() for line in f if line.strip())


def is_real_word(word: str) -> bool:
    return word.upper() in _dictionary()


def score_words(board: list[str], submitted_words: list[str]) -> tuple[list[str], int]:
    """Validates each submitted word (real word, long enough, actually on the board)
    and returns the deduplicated list of valid words plus the total Boggle score.
    The client's claim about which words it found is never trusted for scoring --
    every word is independently re-verified against the board and dictionary here.
    """
    valid_words: list[str] = []
    seen: set[str] = set()
    total_score = 0

    for raw_word in submitted_words:
        word = raw_word.strip().upper()
        if not word or word in seen:
            continue
        if len(word) < MIN_WORD_LENGTH:
            continue
        if not is_real_word(word):
            continue
        if not can_form_word(board, word):
            continue

        seen.add(word)
        valid_words.append(word)
        total_score += score_for_word_length(len(word))

    return valid_words, total_score
