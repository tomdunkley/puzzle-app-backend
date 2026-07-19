def test_submit_score_requires_auth(client, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-01", word="CATS")
    response = client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60})
    assert response.status_code == 401


def test_submit_score_unknown_puzzle(client, auth_headers):
    response = client.post(
        "/v1/scores",
        json={"puzzle_id": "boggle_does-not-exist", "words": ["cats"], "duration_seconds": 60},
        headers=auth_headers("Tom"),
    )
    assert response.status_code == 404


def test_score_is_computed_server_side_not_trusted_from_client(client, auth_headers, seed_puzzle):
    """The client can claim any score it likes -- the server must ignore that and
    compute its own score by re-validating words against the real board+dictionary.
    """
    puzzle_id = seed_puzzle("boggle_2026-01-02", word="CATS")
    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60},
        headers=auth_headers("Tom"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["score"] == 1  # CATS is 4 letters -> 1 point, regardless of what a client might claim
    assert body["valid_words"] == ["CATS"]
    assert body["rank_today"] == 1


def test_submit_score_rejects_words_not_on_board(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-03", word="CATS")
    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "words": ["dogs"], "duration_seconds": 60},
        headers=auth_headers("Tom"),
    )
    assert response.json()["score"] == 0
    assert response.json()["valid_words"] == []


def test_submit_score_includes_current_streak(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    p1 = seed_puzzle("boggle_2026-04-01", word="CATS", date="2026-04-01")
    p2 = seed_puzzle("boggle_2026-04-02", word="CATS", date="2026-04-02")

    first = client.post("/v1/scores", json={"puzzle_id": p1, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    assert first.json()["current_streak"] == 1

    second = client.post("/v1/scores", json={"puzzle_id": p2, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    assert second.json()["current_streak"] == 2

    # Resubmitting a lower score for the same puzzle still reports the current streak.
    resubmit = client.post("/v1/scores", json={"puzzle_id": p2, "words": [], "duration_seconds": 60}, headers=tom)
    assert resubmit.json()["current_streak"] == 2


def test_submit_score_rejects_words_shorter_than_four_letters(client, auth_headers, seed_puzzle):
    # "CAT" is spellable on the board (first 3 letters of CATS) but too short to count.
    puzzle_id = seed_puzzle("boggle_2026-01-04", word="CATS")
    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "words": ["cat"], "duration_seconds": 60},
        headers=auth_headers("Tom"),
    )
    assert response.json()["score"] == 0


def _befriend(client, headers_a, user_id_a, headers_b, user_id_b):
    client.post("/v1/friends/requests", json={"to_user_id": user_id_b}, headers=headers_a)
    client.post(f"/v1/friends/requests/{user_id_a}/accept", headers=headers_b)


def test_leaderboard_requires_auth(client, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-05", word="CATS")
    response = client.get(f"/v1/leaderboards/{puzzle_id}")
    assert response.status_code == 401


def test_leaderboard_orders_by_score_descending(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-05", word="CATS")
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    alex_id = client.get("/v1/users/me", headers=alex).json()["user_id"]
    _befriend(client, tom, tom_id, alex, alex_id)

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": [], "duration_seconds": 60}, headers=alex)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    response = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom)
    entries = response.json()["entries"]
    assert [e["display_name"] for e in entries] == ["Tom", "Alex"]
    assert [e["score"] for e in entries] == [1, 0]


def test_leaderboard_excludes_non_friends(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-07", word="CATS")
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    stranger = auth_headers("Stranger")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    alex_id = client.get("/v1/users/me", headers=alex).json()["user_id"]
    _befriend(client, tom, tom_id, alex, alex_id)

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=alex)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=stranger)

    response = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom)
    entries = response.json()["entries"]
    assert {e["display_name"] for e in entries} == {"Tom", "Alex"}


def test_leaderboard_with_no_friends_shows_only_self(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-01-08", word="CATS")
    tom = auth_headers("Tom")
    auth_headers("Alex")  # unrelated user, never friended

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    response = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom)
    entries = response.json()["entries"]
    assert [e["display_name"] for e in entries] == ["Tom"]


def test_resubmitting_a_lower_score_keeps_the_best(client, auth_headers, seed_puzzle):
    headers = auth_headers("Tom")
    puzzle_id = seed_puzzle("boggle_2026-01-06", word="CATS")

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=headers)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": [], "duration_seconds": 60}, headers=headers)

    leaderboard = client.get(f"/v1/leaderboards/{puzzle_id}", headers=headers).json()
    assert leaderboard["entries"][0]["score"] == 1


def test_leaderboard_breaks_score_ties_by_word_count(client, auth_headers):
    from app.db import scores_table

    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    alex_id = client.get("/v1/users/me", headers=alex).json()["user_id"]
    _befriend(client, tom, tom_id, alex, alex_id)

    puzzle_id = "boggle_2026-02-01"
    scores_table.put_item(
        Item={
            "puzzle_id": puzzle_id,
            "user_id": tom_id,
            "score_id": "sc_tom",
            "score": 2,
            "valid_words": ["CATS"],
            "duration_seconds": 60,
            "submitted_at": "2026-02-01T00:00:00",
        }
    )
    scores_table.put_item(
        Item={
            "puzzle_id": puzzle_id,
            "user_id": alex_id,
            "score_id": "sc_alex",
            "score": 2,
            "valid_words": ["CARS", "CARE"],
            "duration_seconds": 60,
            "submitted_at": "2026-02-01T00:00:00",
        }
    )

    leaderboard = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom).json()
    entries = leaderboard["entries"]
    assert [e["display_name"] for e in entries] == ["Alex", "Tom"]
    assert [e["word_count"] for e in entries] == [2, 1]

    detail = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=tom).json()
    assert detail["rank_today"] == 2


def test_leaderboard_includes_avatar_id(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    client.patch("/v1/users/me", json={"avatar_id": "words"}, headers=tom)
    puzzle_id = seed_puzzle("boggle_2026-01-09", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    leaderboard = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom).json()
    assert leaderboard["entries"][0]["avatar_id"] == "words"


def test_leaderboard_includes_avatar_color_id(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    client.patch("/v1/users/me", json={"avatar_color_id": "blue"}, headers=tom)
    puzzle_id = seed_puzzle("boggle_2026-01-10", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    leaderboard = client.get(f"/v1/leaderboards/{puzzle_id}", headers=tom).json()
    assert leaderboard["entries"][0]["avatar_color_id"] == "blue"


def test_streak_starts_at_one_on_first_play(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    puzzle_id = seed_puzzle("boggle_2026-02-01", word="CATS", date="2026-02-01")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    streak = client.get("/v1/users/me", headers=tom).json()["streaks"]["boggle"]
    assert streak == {"current": 1, "longest": 1, "last_played_date": "2026-02-01"}


def test_streak_increments_on_consecutive_days(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    p1 = seed_puzzle("boggle_2026-02-01", word="CATS", date="2026-02-01")
    p2 = seed_puzzle("boggle_2026-02-02", word="CATS", date="2026-02-02")
    client.post("/v1/scores", json={"puzzle_id": p1, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": p2, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    streak = client.get("/v1/users/me", headers=tom).json()["streaks"]["boggle"]
    assert streak["current"] == 2
    assert streak["longest"] == 2


def test_streak_resets_after_a_gap_but_keeps_longest(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    p1 = seed_puzzle("boggle_2026-02-01", word="CATS", date="2026-02-01")
    p2 = seed_puzzle("boggle_2026-02-02", word="CATS", date="2026-02-02")
    p3 = seed_puzzle("boggle_2026-02-05", word="CATS", date="2026-02-05")  # gap: skipped 03 and 04
    client.post("/v1/scores", json={"puzzle_id": p1, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": p2, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": p3, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    streak = client.get("/v1/users/me", headers=tom).json()["streaks"]["boggle"]
    assert streak["current"] == 1
    assert streak["longest"] == 2


def test_streak_does_not_double_count_same_day_resubmission(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    puzzle_id = seed_puzzle("boggle_2026-02-01", word="CATS", date="2026-02-01")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": [], "duration_seconds": 60}, headers=tom)

    streak = client.get("/v1/users/me", headers=tom).json()["streaks"]["boggle"]
    assert streak["current"] == 1


def test_score_detail_requires_auth(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzle_id = seed_puzzle("boggle_2026-03-01", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    assert client.get(f"/v1/scores/{puzzle_id}/{tom_id}").status_code == 401


def test_score_detail_self_can_view(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzle_id = seed_puzzle("boggle_2026-03-02", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=tom)
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Tom"
    assert body["score"] == 1
    assert body["valid_words"] == ["CATS"]
    assert body["rank_today"] == 1
    assert body["locked"] is False
    assert len(body["board"]) == 25


def test_score_detail_viewer_who_has_played_sees_full_detail(client, auth_headers, seed_puzzle):
    """Friendship no longer gates the board/words -- having completed the same puzzle
    yourself does. This also covers the global leaderboard, where viewer and viewee
    are typically strangers.
    """
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzle_id = seed_puzzle("boggle_2026-03-03", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=alex)

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=alex)
    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is False
    assert body["valid_words"] == ["CATS"]
    assert len(body["board"]) == 25


def test_score_detail_locked_for_viewer_who_has_not_played(client, auth_headers, seed_puzzle):
    """No spoilers: someone who hasn't completed today's puzzle yet can still see a
    leaderboard entry's basic performance info, but not the board/words behind it --
    whether or not they're friends with the player.
    """
    tom = auth_headers("Tom")
    stranger = auth_headers("Stranger")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzle_id = seed_puzzle("boggle_2026-03-04", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=stranger)
    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is True
    assert body["score"] == 1
    assert body["rank_today"] == 1
    assert body["valid_words"] is None
    assert body["board"] is None


def test_score_detail_numbers_locked_hides_numbers_and_target(client, auth_headers):
    from app.db import puzzles_table

    tom = auth_headers("Tom")
    stranger = auth_headers("Stranger")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzles_table.put_item(
        Item={
            "puzzle_id": "numbers_2026-03-07",
            "game": "numbers",
            "date": "2026-03-07",
            "numbers": [100, 75, 50, 25, 2, 2],
            "target": 200,
            "solution": [],
            "duration_seconds": 60,
        }
    )
    client.post(
        "/v1/scores",
        json={"puzzle_id": "numbers_2026-03-07", "result_value": 100, "steps": [], "duration_seconds": 30},
        headers=tom,
    )

    response = client.get(f"/v1/scores/numbers_2026-03-07/{tom_id}", headers=stranger)
    body = response.json()
    assert body["locked"] is True
    assert body["numbers"] is None
    assert body["target"] is None
    assert body["steps"] is None
    assert body["distance"] == 100  # basic performance info stays visible


def test_score_detail_includes_avatar_color_id(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    client.patch("/v1/users/me", json={"avatar_color_id": "orange"}, headers=tom)
    puzzle_id = seed_puzzle("boggle_2026-03-06", word="CATS")
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=tom)
    assert response.json()["avatar_color_id"] == "orange"


def test_global_leaderboard_requires_auth(client, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-10", word="CATS")
    assert client.get(f"/v1/leaderboards/{puzzle_id}/global").status_code == 401


def test_global_leaderboard_includes_non_friends(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-11", word="CATS")
    tom = auth_headers("Tom")
    stranger = auth_headers("Stranger")  # never friended Tom

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=stranger
    )

    entries = client.get(f"/v1/leaderboards/{puzzle_id}/global", headers=tom).json()["entries"]
    assert {e["display_name"] for e in entries} == {"Tom", "Stranger"}


def test_global_leaderboard_caps_at_top_ten(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-12", word="CATS")
    headers = [auth_headers(f"Player{i}") for i in range(11)]
    for headers_for_player in headers:
        client.post(
            "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60},
            headers=headers_for_player,
        )

    entries = client.get(f"/v1/leaderboards/{puzzle_id}/global", headers=headers[0]).json()["entries"]
    assert len(entries) == 10
    assert [e["rank"] for e in entries] == list(range(1, 11))


def test_global_leaderboard_excludes_guests(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-14", word="CATS")
    tom = auth_headers("Tom")
    guest = client.post("/v1/auth/guest").json()
    guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=guest_headers
    )

    entries = client.get(f"/v1/leaderboards/{puzzle_id}/global", headers=tom).json()["entries"]
    assert [e["display_name"] for e in entries] == ["Tom"]


def test_global_leaderboard_excludes_opted_out_users(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-13", word="CATS")
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    client.patch("/v1/users/me", json={"visible_on_global_leaderboard": False}, headers=alex)

    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom)
    client.post("/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=alex)

    entries = client.get(f"/v1/leaderboards/{puzzle_id}/global", headers=tom).json()["entries"]
    assert [e["display_name"] for e in entries] == ["Tom"]
    assert entries[0]["rank"] == 1


def test_opted_out_user_gets_no_global_rank(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-15", word="CATS")
    alex = auth_headers("Alex")
    client.patch("/v1/users/me", json={"visible_on_global_leaderboard": False}, headers=alex)

    body = client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=alex
    ).json()
    assert body["rank_today"] == 0


def test_opted_out_users_score_does_not_count_toward_others_rank(client, auth_headers, seed_puzzle):
    puzzle_id = seed_puzzle("boggle_2026-04-16", word="STEAK")
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    client.patch("/v1/users/me", json={"visible_on_global_leaderboard": False}, headers=alex)

    # Alex's higher score should not push Tom down to rank 2 -- it's invisible to
    # everyone else's ranking, not just to the public leaderboard list.
    client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["steak"], "duration_seconds": 60}, headers=alex
    )
    body = client.post(
        "/v1/scores", json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 60}, headers=tom
    ).json()
    assert body["rank_today"] == 1


def test_score_detail_missing_score_404s(client, auth_headers, seed_puzzle):
    tom = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    puzzle_id = seed_puzzle("boggle_2026-03-05", word="CATS")

    response = client.get(f"/v1/scores/{puzzle_id}/{tom_id}", headers=tom)
    assert response.status_code == 404
