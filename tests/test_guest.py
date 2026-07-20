def _guest_headers(client) -> tuple[dict, str]:
    response = client.post("/v1/auth/guest")
    assert response.status_code == 201, response.text
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}, access_token


def _play_today(client, headers) -> dict:
    puzzle = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers).json()
    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle["puzzle_id"], "words": [], "duration_seconds": 30},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return {**response.json(), "puzzle_id": puzzle["puzzle_id"]}


def test_guest_sign_in_issues_usable_tokens(client):
    headers, _ = _guest_headers(client)
    me = client.get("/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"].startswith("Guest")
    assert me.json()["email_verified"] is True


def test_guest_can_play_without_email_verification(client):
    headers, _ = _guest_headers(client)
    puzzle = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    assert puzzle.status_code == 200

    response = client.post(
        "/v1/scores",
        json={"puzzle_id": puzzle.json()["puzzle_id"], "words": [], "duration_seconds": 30},
        headers=headers,
    )
    assert response.status_code == 201


def test_guest_score_does_not_accrue_a_streak(client):
    headers, _ = _guest_headers(client)
    result = _play_today(client, headers)
    assert result["current_streak"] == 0

    me = client.get("/v1/users/me", headers=headers).json()
    assert me["streaks"] == {}


def test_guest_score_carries_the_guests_own_ttl(client):
    from app.db import scores_table, users_table

    headers, guest_token = _guest_headers(client)
    played = _play_today(client, headers)

    from app.auth.jwt import decode_token

    guest_user_id = decode_token(guest_token, expected_type="access")
    guest_user = users_table.get_item(Key={"user_id": guest_user_id}).get("Item")
    score_item = scores_table.get_item(
        Key={"puzzle_id": played["puzzle_id"], "user_id": guest_user_id}
    ).get("Item")

    assert score_item["guest_expires_at_epoch"] == guest_user["guest_expires_at_epoch"]


def test_real_user_score_never_sets_a_ttl(client, auth_headers):
    from app.db import scores_table

    tom = auth_headers("Tom")
    tom_id = client.get("/v1/users/me", headers=tom).json()["user_id"]
    played = _play_today(client, tom)

    score_item = scores_table.get_item(Key={"puzzle_id": played["puzzle_id"], "user_id": tom_id}).get("Item")
    assert "guest_expires_at_epoch" not in score_item


def test_registering_claims_todays_guest_score(client):
    guest_headers, guest_token = _guest_headers(client)
    played = _play_today(client, guest_headers)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "tom@example.com",
            "password": "correct-horse",
            "guest_access_token": guest_token,
        },
    )
    assert register.status_code == 201
    new_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    new_user_id = client.get("/v1/users/me", headers=new_headers).json()["user_id"]

    detail = client.get(f"/v1/scores/{played['puzzle_id']}/{new_user_id}", headers=new_headers)
    assert detail.status_code == 200
    assert detail.json()["score"] == played["score"]

    # The claimed score is the new account's first play -- streak starts at 1, even
    # though guests themselves never accrue one.
    me = client.get("/v1/users/me", headers=new_headers).json()
    assert me["streaks"]["boggle"]["current"] == 1


def test_guest_account_is_deleted_after_claim(client):
    guest_headers, guest_token = _guest_headers(client)
    _play_today(client, guest_headers)

    client.post(
        "/v1/auth/register",
        json={
            "email": "tom@example.com",
            "password": "correct-horse",
            "guest_access_token": guest_token,
        },
    )

    stale = client.get("/v1/users/me", headers=guest_headers)
    assert stale.status_code == 404


def test_guest_score_is_dropped_if_account_already_played_today_elsewhere(client, auth_headers):
    # auth_headers (dev-login) gives a pre-verified account so it can play immediately,
    # standing in for "Tom already played today on another device" before this login.
    real_headers = auth_headers("Tom")
    real_played = _play_today(client, real_headers)
    real_user_id = client.get("/v1/users/me", headers=real_headers).json()["user_id"]

    guest_headers, guest_token = _guest_headers(client)
    _play_today(client, guest_headers)

    # Simulate that same "Tom" identity signing back in elsewhere, carrying a guest
    # token from this device -- exercised directly against the service layer since
    # dev-login has no password to log back in with via the public API.
    from app.services.guest_service import claim_guest_score_for_today

    claim_guest_score_for_today(real_user_id, guest_token)

    detail = client.get(f"/v1/scores/{real_played['puzzle_id']}/{real_user_id}", headers=real_headers)
    assert detail.json()["score"] == real_played["score"]

    # The guest is still cleaned up even though nothing was transferred.
    assert client.get("/v1/users/me", headers=guest_headers).status_code == 404


def test_claim_is_a_no_op_with_no_guest_token(client):
    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse"},
    )
    assert register.status_code == 201


def test_claim_silently_ignores_a_garbage_guest_token(client):
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "tom@example.com",
            "password": "correct-horse",
            "guest_access_token": "not-a-real-token",
        },
    )
    assert register.status_code == 201
