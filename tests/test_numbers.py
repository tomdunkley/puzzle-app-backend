from app.services.numbers_game import (
    BIG_NUMBERS,
    InvalidNumbersAttemptError,
    generate_round,
    validate_numbers_attempt,
)


def _seed_numbers_puzzle(
    puzzle_id: str, numbers: list[int], target: int, solution: list[dict] | None = None, date: str = "2026-05-01"
) -> str:
    from app.db import puzzles_table

    puzzles_table.put_item(
        Item={
            "puzzle_id": puzzle_id,
            "game": "numbers",
            "date": date,
            "numbers": numbers,
            "target": target,
            "solution": solution or [],
            "duration_seconds": 60,
        }
    )
    return puzzle_id


# ---- solver ----------------------------------------------------------------


def test_generate_round_is_deterministic_per_seed():
    first = generate_round("numbers_2026-05-01")
    second = generate_round("numbers_2026-05-01")
    assert first == second


def test_generate_round_produces_six_numbers_with_valid_bigs_and_smalls():
    round_ = generate_round("numbers_2026-05-02")
    numbers = round_["numbers"]
    assert len(numbers) == 6

    bigs = [n for n in numbers if n in BIG_NUMBERS]
    smalls = [n for n in numbers if n not in BIG_NUMBERS]
    assert 1 <= len(bigs) <= 4
    assert len(set(bigs)) == len(bigs)  # no duplicate bigs
    assert all(1 <= n <= 10 for n in smalls)

    # Bigs are listed before smalls (Countdown convention) -- no interleaving.
    assert numbers[: len(bigs)] == bigs
    assert numbers[len(bigs) :] == smalls


def test_generate_round_target_is_three_digits_and_solvable():
    round_ = generate_round("numbers_2026-05-03")
    assert 100 <= round_["target"] <= 999

    result = validate_numbers_attempt(
        round_["numbers"], round_["target"], round_["solution"][-1]["result"], round_["solution"]
    )
    assert result["distance"] == 0


def test_validate_numbers_attempt_with_no_steps_uses_a_starting_number():
    result = validate_numbers_attempt([100, 75, 50, 25, 3, 7], 300, 75, [])
    assert result == {"result_value": 75, "distance": 225, "steps": []}


def test_validate_numbers_attempt_rejects_a_value_not_in_the_starting_numbers():
    try:
        validate_numbers_attempt([100, 75, 50, 25, 3, 7], 300, 99, [])
        assert False, "expected InvalidNumbersAttemptError"
    except InvalidNumbersAttemptError:
        pass


def test_validate_numbers_attempt_replays_a_legal_sequence():
    steps = [{"a": 50, "op": "*", "b": 3, "result": 150}, {"a": 150, "op": "+", "b": 7, "result": 157}]
    result = validate_numbers_attempt([100, 75, 50, 25, 3, 7], 157, 157, steps)
    assert result == {"result_value": 157, "distance": 0, "steps": steps}


def test_validate_numbers_attempt_rejects_reusing_a_consumed_number():
    # 50 only appears once -- using it in two separate first steps is illegal.
    steps = [
        {"a": 50, "op": "*", "b": 3, "result": 150},
        {"a": 50, "op": "+", "b": 7, "result": 57},
    ]
    try:
        validate_numbers_attempt([100, 75, 50, 25, 3, 7], 999, 57, steps)
        assert False, "expected InvalidNumbersAttemptError"
    except InvalidNumbersAttemptError:
        pass


def test_validate_numbers_attempt_rejects_a_tampered_result():
    steps = [{"a": 50, "op": "*", "b": 3, "result": 9999}]
    try:
        validate_numbers_attempt([100, 75, 50, 25, 3, 7], 9999, 9999, steps)
        assert False, "expected InvalidNumbersAttemptError"
    except InvalidNumbersAttemptError:
        pass


def test_validate_numbers_attempt_rejects_inexact_division():
    steps = [{"a": 7, "op": "/", "b": 3, "result": 2}]
    try:
        validate_numbers_attempt([100, 75, 50, 25, 3, 7], 2, 2, steps)
        assert False, "expected InvalidNumbersAttemptError"
    except InvalidNumbersAttemptError:
        pass


def test_validate_numbers_attempt_rejects_negative_subtraction():
    steps = [{"a": 3, "op": "-", "b": 7, "result": -4}]
    try:
        validate_numbers_attempt([100, 75, 50, 25, 3, 7], -4, -4, steps)
        assert False, "expected InvalidNumbersAttemptError"
    except InvalidNumbersAttemptError:
        pass


# ---- API --------------------------------------------------------------------


def test_list_games_includes_numbers(client):
    response = client.get("/v1/games")
    games = response.json()
    assert any(g["game"] == "numbers" for g in games)


def test_today_numbers_puzzle_is_stable_and_unplayed(client, auth_headers):
    headers = auth_headers("Tom")
    first = client.get("/v1/puzzles/today", params={"game": "numbers"}, headers=headers).json()
    second = client.get("/v1/puzzles/today", params={"game": "numbers"}, headers=headers).json()

    assert first["numbers"] == second["numbers"]
    assert first["target"] == second["target"]
    assert len(first["numbers"]) == 6
    assert first["duration_seconds"] == 60
    assert first["already_played"] is False
    assert first["your_distance"] is None


def test_submit_numbers_score_with_steps(client, auth_headers):
    headers = auth_headers("Tom")
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-10", [100, 75, 50, 25, 3, 7], target=157)

    response = client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 40,
            "steps": [
                {"a": 50, "op": "*", "b": 3, "result": 150},
                {"a": 150, "op": "+", "b": 7, "result": 157},
            ],
            "result_value": 157,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result_value"] == 157
    assert body["distance"] == 0
    assert body["rank_today"] == 1
    assert len(body["steps"]) == 2


def test_submit_numbers_score_with_no_steps(client, auth_headers):
    headers = auth_headers("Tom")
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-11", [100, 75, 50, 25, 3, 7], target=300)

    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "duration_seconds": 5, "result_value": 75},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result_value"] == 75
    assert body["distance"] == 225


def test_submit_numbers_score_rejects_invalid_steps(client, auth_headers):
    headers = auth_headers("Tom")
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-12", [100, 75, 50, 25, 3, 7], target=157)

    response = client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 40,
            "steps": [{"a": 50, "op": "*", "b": 3, "result": 9999}],
            "result_value": 9999,
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_resubmitting_a_worse_numbers_attempt_keeps_the_best(client, auth_headers):
    headers = auth_headers("Tom")
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-13", [100, 75, 50, 25, 3, 7], target=157)

    client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 40,
            "steps": [
                {"a": 50, "op": "*", "b": 3, "result": 150},
                {"a": 150, "op": "+", "b": 7, "result": 157},
            ],
            "result_value": 157,
        },
        headers=headers,
    )
    worse = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "duration_seconds": 50, "result_value": 75},
        headers=headers,
    )
    assert worse.json()["distance"] == 0
    assert worse.json()["result_value"] == 157


def test_numbers_streak_is_independent_of_boggle(client, auth_headers):
    tom = auth_headers("Tom")
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-14", [100, 75, 50, 25, 3, 7], target=300, date="2026-05-14")

    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "duration_seconds": 10, "result_value": 75},
        headers=tom,
    )
    streaks = client.get("/v1/users/me", headers=tom).json()["streaks"]
    assert streaks["numbers"]["current"] == 1
    assert "boggle" not in streaks


def test_numbers_leaderboard_ranks_by_closeness_then_duration(client, auth_headers):
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-15", [100, 75, 50, 25, 3, 7], target=300)
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    alex_id = client.get("/v1/users/me", headers=alex).json()["user_id"]
    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    client.post(f"/v1/friends/requests/{tom_id}/accept", headers=alex)

    # Tom: distance 0, slower. Alex: distance 0, faster -- should rank first on tiebreak.
    client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 55,
            "steps": [
                {"a": 50, "op": "*", "b": 3, "result": 150},
                {"a": 150, "op": "*", "b": 100, "result": 15000},
            ],
            "result_value": 15000,
        },
        headers=tom,
    )
    # Give Tom an exact match instead, slower than Alex's.
    client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 55,
            "steps": [{"a": 75, "op": "+", "b": 25, "result": 100}, {"a": 100, "op": "*", "b": 3, "result": 300}],
            "result_value": 300,
        },
        headers=tom,
    )
    client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 20,
            "steps": [{"a": 75, "op": "+", "b": 25, "result": 100}, {"a": 100, "op": "*", "b": 3, "result": 300}],
            "result_value": 300,
        },
        headers=alex,
    )

    entries = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom).json()["entries"]
    assert [e["display_name"] for e in entries] == ["Alex", "Tom"]
    assert [e["distance"] for e in entries] == [0, 0]
    assert [e["duration_seconds"] for e in entries] == [20, 55]
    assert entries[0]["score"] is None
    assert entries[0]["word_count"] is None


def test_numbers_score_detail_shows_steps(client, auth_headers):
    headers = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=headers).json()["user_id"]
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-16", [100, 75, 50, 25, 3, 7], target=157)

    client.post(
        "/v1/scores",
        json={
            "puzzle_id": puzzle_id,
            "duration_seconds": 40,
            "steps": [
                {"a": 50, "op": "*", "b": 3, "result": 150},
                {"a": 150, "op": "+", "b": 7, "result": 157},
            ],
            "result_value": 157,
        },
        headers=headers,
    )

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["game"] == "numbers"
    assert body["numbers"] == [100, 75, 50, 25, 3, 7]
    assert body["target"] == 157
    assert body["result_value"] == 157
    assert body["distance"] == 0
    assert len(body["steps"]) == 2


def test_numbers_global_leaderboard_excludes_guests(client, auth_headers):
    puzzle_id = _seed_numbers_puzzle("numbers_2026-05-17", [100, 75, 50, 25, 3, 7], target=300)
    tom = auth_headers("Tom")
    guest = client.post("/v1/auth/guest").json()
    guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}

    client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "duration_seconds": 10, "result_value": 75}, headers=tom
    )
    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "duration_seconds": 10, "result_value": 75},
        headers=guest_headers,
    )

    entries = client.get(f"/v1/leaderboards/{puzzle_id}/global", headers=tom).json()["entries"]
    assert [e["display_name"] for e in entries] == ["Tom"]


def test_guest_numbers_score_is_claimed_on_register(client):
    puzzle_id_today_marker = "numbers"  # the claim flow uses get_or_create_today_puzzle, not a seeded id
    guest = client.post("/v1/auth/guest").json()
    guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}

    puzzle = client.get("/v1/puzzles/today", params={"game": puzzle_id_today_marker}, headers=guest_headers).json()
    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle["puzzle_id"], "duration_seconds": 10, "result_value": puzzle["numbers"][0]},
        headers=guest_headers,
    )

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "numbersguest@example.com",
            "password": "correct-horse",
            "guest_access_token": guest["access_token"],
        },
    )
    assert register.status_code == 201
    new_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    new_user_id = client.get("/v1/users/me", headers=new_headers).json()["user_id"]

    detail = client.get(f"/v1/scores/{puzzle['puzzle_id']}/{new_user_id}", headers=new_headers)
    assert detail.status_code == 200
    assert detail.json()["result_value"] == puzzle["numbers"][0]
