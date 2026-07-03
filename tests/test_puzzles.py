def test_today_puzzle_requires_auth(client):
    response = client.get("/v1/puzzles/today", params={"game": "boggle"})
    assert response.status_code == 401


def test_today_puzzle_is_stable_across_requests(client, auth_headers):
    headers = auth_headers("Tom")
    first = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    second = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)

    assert first.status_code == 200
    assert first.json()["board"] == second.json()["board"]
    assert len(first.json()["board"]) == 25


def test_today_puzzle_starts_unplayed(client, auth_headers):
    response = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=auth_headers("Tom"))
    body = response.json()
    assert body["already_played"] is False
    assert body["your_score"] is None


def test_today_puzzle_uses_90_second_duration(client, auth_headers):
    response = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=auth_headers("Tom"))
    assert response.json()["duration_seconds"] == 90


def test_get_puzzle_by_id_not_found(client, auth_headers):
    response = client.get("/v1/puzzles/boggle_1999-01-01", headers=auth_headers("Tom"))
    assert response.status_code == 404


def test_today_puzzle_reflects_submitted_score(client, auth_headers, seed_puzzle):
    headers = auth_headers("Tom")
    puzzle_id = seed_puzzle("boggle_2026-02-01", word="CATS")

    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle_id, "words": ["cats"], "duration_seconds": 120},
        headers=headers,
    )

    response = client.get(f"/v1/puzzles/{puzzle_id}", headers=headers)
    body = response.json()
    assert body["already_played"] is True
    assert body["your_score"] == 1
