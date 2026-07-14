import random
from collections import Counter

BIG_NUMBERS = [25, 50, 75, 100]
TARGET_MIN = 100
TARGET_MAX = 999

_BIG_NUMBERS = frozenset({25, 50, 75, 100})
_SOLUTION_CAP = 200


class InvalidNumbersAttemptError(Exception):
    pass


def _apply(a: int, op: str, b: int) -> int:
    """Computes a single step's result under the same legality rules the Android
    client enforces before ever letting a player confirm a combine: no negative or
    zero subtraction, no inexact division. Re-derived here rather than trusted from
    the client, exactly like Boggle re-validates words against the board.
    """
    if op == "+":
        return a + b
    if op == "-":
        if a <= b:
            raise InvalidNumbersAttemptError("subtraction must produce a positive result")
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0 or a % b != 0:
            raise InvalidNumbersAttemptError("division must be exact")
        return a // b
    raise InvalidNumbersAttemptError(f"unknown operator {op!r}")


def _combine_options(a: int, b: int) -> list[tuple[int, str, int, int]]:
    """Every legal (left, op, right, result) combination of a and b -- used only for
    generating/solving a round (enumerating possibilities), not for validating a
    specific player-submitted step (see _apply).
    """
    options = [(a, "+", b, a + b), (a, "*", b, a * b)]
    if a > b:
        options.append((a, "-", b, a - b))
    elif b > a:
        options.append((b, "-", a, b - a))
    if b != 0 and a % b == 0:
        options.append((a, "/", b, a // b))
    if a != 0 and b % a == 0 and a != b:
        options.append((b, "/", a, b // a))
    return options


def find_reachable(numbers: list[int]) -> dict[int, list[dict]]:
    """Every value reachable from some subset of `numbers` (you never have to use
    all six), each mapped to one example sequence of steps that reaches it. Explores
    every way of repeatedly combining two tiles into one, memoized on the sorted
    multiset of remaining tile values so equivalent states (very common given
    duplicate small numbers) are only explored once.
    """
    reachable: dict[int, list[dict]] = {}
    seen_states: set[tuple[int, ...]] = set()

    def visit(tiles: list[dict]) -> None:
        state = tuple(sorted(t["value"] for t in tiles))
        if state in seen_states:
            return
        seen_states.add(state)
        for tile in tiles:
            reachable.setdefault(tile["value"], tile["steps"])
        if len(tiles) < 2:
            return
        for i in range(len(tiles)):
            for j in range(i + 1, len(tiles)):
                a_tile, b_tile = tiles[i], tiles[j]
                rest = [t for k, t in enumerate(tiles) if k != i and k != j]
                for left, op, right, result in _combine_options(a_tile["value"], b_tile["value"]):
                    step = {"a": left, "op": op, "b": right, "result": result}
                    new_tile = {"value": result, "steps": a_tile["steps"] + b_tile["steps"] + [step]}
                    visit(rest + [new_tile])

    visit([{"value": n, "steps": []} for n in numbers])
    return reachable


def _human_score(steps: list[dict]) -> tuple:
    """Lower is more human-like. Priority: fewest steps → big numbers early → smallest
    max intermediate → roundest intermediate values.
    """
    n = len(steps)
    big_early = -sum(
        (n - i) for i, s in enumerate(steps)
        if s["a"] in _BIG_NUMBERS or s["b"] in _BIG_NUMBERS
    )
    max_intermediate = max((s["result"] for s in steps), default=0)
    round_score = -sum(
        4 if s["result"] % 100 == 0 else
        3 if s["result"] % 50 == 0 else
        2 if s["result"] % 25 == 0 else
        1 if s["result"] % 10 == 0 else
        0 if s["result"] % 5 == 0 else -1
        for s in steps
    )
    return (n, big_early, max_intermediate, round_score)


def find_best_solution(numbers: list[int], target: int) -> list[dict]:
    """Collects up to _SOLUTION_CAP solutions then returns the most human-like one.
    Re-uses the same memoized DFS as find_reachable but gathers all paths to the
    target rather than stopping at the first.
    """
    if target in numbers:
        return []

    solutions: list[list[dict]] = []
    seen_states: set[tuple[int, ...]] = set()

    def visit(tiles: list[dict]) -> None:
        if len(solutions) >= _SOLUTION_CAP:
            return
        state = tuple(sorted(t["value"] for t in tiles))
        if state in seen_states:
            return
        seen_states.add(state)
        for tile in tiles:
            if tile["value"] == target and tile["steps"]:
                solutions.append(tile["steps"])
                if len(solutions) >= _SOLUTION_CAP:
                    return
        if len(tiles) < 2:
            return
        for i in range(len(tiles)):
            for j in range(i + 1, len(tiles)):
                if len(solutions) >= _SOLUTION_CAP:
                    return
                a_tile, b_tile = tiles[i], tiles[j]
                rest = [t for k, t in enumerate(tiles) if k != i and k != j]
                for left, op, right, result in _combine_options(a_tile["value"], b_tile["value"]):
                    step = {"a": left, "op": op, "b": right, "result": result}
                    new_tile = {"value": result, "steps": a_tile["steps"] + b_tile["steps"] + [step]}
                    visit(rest + [new_tile])

    visit([{"value": n, "steps": []} for n in numbers])
    return min(solutions, key=_human_score) if solutions else []


def generate_round(seed: str) -> dict:
    """Deterministic round for a given seed (e.g. "numbers_2026-06-27"): 0-4 distinct
    big numbers (25/50/75/100) plus small numbers (1-10, duplicates allowed) filling
    the rest of six, and a 3-digit target chosen from what's actually reachable --
    so a solution is guaranteed to exist by construction, never by luck. The bigs are
    listed before the smalls (Countdown convention), each group in random order.
    """
    rng = random.Random(seed)
    for _attempt in range(50):
        big_count = rng.randint(0, 4)
        bigs = rng.sample(BIG_NUMBERS, big_count)
        smalls = [rng.randint(1, 10) for _ in range(6 - big_count)]
        numbers = bigs + smalls

        reachable = find_reachable(numbers)
        targets = sorted(v for v in reachable if TARGET_MIN <= v <= TARGET_MAX)
        if not targets:
            continue
        target = rng.choice(targets)
        return {"numbers": numbers, "target": target, "solution": find_best_solution(numbers, target)}
    raise RuntimeError("failed to generate a solvable numbers round")


def validate_numbers_attempt(
    numbers: list[int], target: int, result_value: int | None, steps: list[dict]
) -> dict:
    """Replays a player's claimed derivation against the puzzle's actual starting
    numbers -- the submitted result_value and steps are evidence, never trusted
    outright. Raises InvalidNumbersAttemptError if any step uses an operand that
    isn't actually available or claims an arithmetically wrong result.
    """
    if result_value is None:
        raise InvalidNumbersAttemptError("result_value is required")

    available = Counter(numbers)
    last_result = None
    validated_steps = []

    for step in steps:
        a, op, b = step["a"], step["op"], step["b"]
        if available[a] <= 0:
            raise InvalidNumbersAttemptError(f"{a} is not available")
        available[a] -= 1
        if available[b] <= 0:
            available[a] += 1
            raise InvalidNumbersAttemptError(f"{b} is not available")
        available[b] -= 1

        result = _apply(a, op, b)
        available[result] += 1
        validated_steps.append({"a": a, "op": op, "b": b, "result": result})
        last_result = result

    if validated_steps:
        final_value = last_result
        if final_value != result_value:
            raise InvalidNumbersAttemptError("result_value does not match the final step")
    else:
        final_value = result_value
        if available[final_value] <= 0:
            raise InvalidNumbersAttemptError("result_value is not one of the available numbers")

    return {
        "result_value": final_value,
        "distance": abs(target - final_value),
        "steps": validated_steps,
    }
