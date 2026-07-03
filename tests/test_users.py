def _user_id(client, headers):
    return client.get("/v1/users/me", headers=headers).json()["user_id"]


def test_update_display_name_succeeds(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"display_name": "Thomas"}, headers=tom)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Thomas"


def test_update_display_name_rejects_duplicate(client, auth_headers):
    auth_headers("Alex")
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"display_name": "Alex"}, headers=tom)
    assert response.status_code == 409


def test_update_display_name_allows_keeping_own_name(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"display_name": "Tom"}, headers=tom)
    assert response.status_code == 200


def test_update_display_name_rejects_at_sign(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"display_name": "Tom@Puzzles"}, headers=tom)
    assert response.status_code == 422


def test_update_avatar_succeeds(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"avatar_id": "dice"}, headers=tom)
    assert response.status_code == 200
    assert response.json()["avatar_id"] == "dice"


def test_update_avatar_rejects_invalid_id(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"avatar_id": "not-a-real-avatar"}, headers=tom)
    assert response.status_code == 400


def test_update_avatar_color_succeeds(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"avatar_color_id": "green"}, headers=tom)
    assert response.status_code == 200
    assert response.json()["avatar_color_id"] == "green"


def test_update_avatar_color_rejects_invalid_id(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"avatar_color_id": "not-a-real-color"}, headers=tom)
    assert response.status_code == 400


def test_visible_on_global_leaderboard_defaults_true(client, auth_headers):
    tom = auth_headers("Tom")
    assert client.get("/v1/users/me", headers=tom).json()["visible_on_global_leaderboard"] is True


def test_update_visible_on_global_leaderboard(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.patch("/v1/users/me", json={"visible_on_global_leaderboard": False}, headers=tom)
    assert response.status_code == 200
    assert response.json()["visible_on_global_leaderboard"] is False


def test_users_me_requires_auth(client):
    assert client.get("/v1/users/me").status_code == 401
    assert client.patch("/v1/users/me", json={"avatar_id": "dice"}).status_code == 401


def test_update_streak_for_play_is_idempotent_per_date(client, auth_headers):
    from app.services.user_service import update_streak_for_play

    tom_id = _user_id(client, auth_headers("Tom"))
    update_streak_for_play(tom_id, "boggle", "2026-02-01")
    streak = update_streak_for_play(tom_id, "boggle", "2026-02-01")
    assert streak["current"] == 1
