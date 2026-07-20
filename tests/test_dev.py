from app.services.score_service import get_user_score_item
from app.services.user_service import mark_email_verified


def _register(client, email):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "correct-horse"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_non_developer_cannot_reset_progress(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.post("/v1/dev/reset-progress", headers=tom)
    assert response.status_code == 403


def test_reset_progress_requires_auth(client):
    assert client.post("/v1/dev/reset-progress").status_code == 401


def test_developer_flag_reflected_on_profile(client, auth_headers):
    tom = auth_headers("Tom")
    dev = _register(client, "dunkertheepic13@gmail.com")

    assert client.get("/v1/users/me", headers=tom).json()["is_developer"] is False
    assert client.get("/v1/users/me", headers=dev).json()["is_developer"] is True


def test_developer_can_reset_todays_progress(client):
    dev = _register(client, "dunkertheepic13@gmail.com")
    dev_id = client.get("/v1/users/me", headers=dev).json()["user_id"]
    mark_email_verified(dev_id)

    puzzle = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=dev).json()
    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle["puzzle_id"], "words": [], "duration_seconds": 30},
        headers=dev,
    )
    assert get_user_score_item(puzzle["puzzle_id"], dev_id) is not None

    assert client.post("/v1/dev/reset-progress", headers=dev).status_code == 200
    assert get_user_score_item(puzzle["puzzle_id"], dev_id) is None


def test_reset_progress_only_clears_developers_own_scores(client, auth_headers):
    dev = _register(client, "dunkertheepic13@gmail.com")
    dev_id = client.get("/v1/users/me", headers=dev).json()["user_id"]
    mark_email_verified(dev_id)
    tom = auth_headers("Tom")

    puzzle = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=dev).json()
    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle["puzzle_id"], "words": [], "duration_seconds": 30},
        headers=dev,
    )
    client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle["puzzle_id"], "words": [], "duration_seconds": 30},
        headers=tom,
    )
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]

    client.post("/v1/dev/reset-progress", headers=dev)
    assert get_user_score_item(puzzle["puzzle_id"], tom_id) is not None
