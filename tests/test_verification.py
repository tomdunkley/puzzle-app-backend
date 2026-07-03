def _register(client, email="tom@example.com", display_name="Tom"):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "correct-horse", "display_name": display_name},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_sends_a_verification_code(client, mock_send_email):
    _register(client)
    assert len(mock_send_email) == 1
    assert mock_send_email[0]["to_address"] == "tom@example.com"


def test_new_user_is_unverified_and_blocked_from_gameplay(client):
    headers = _register(client)
    me = client.get("/v1/users/me", headers=headers)
    assert me.json()["email_verified"] is False

    today = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    assert today.status_code == 403

    score = client.post(
        "/v1/scores",
        json={"puzzle_id": "boggle_1999-01-01", "words": [], "duration_seconds": 1},
        headers=headers,
    )
    assert score.status_code == 403


def test_correct_code_verifies_and_unblocks_gameplay(client, mock_send_email):
    headers = _register(client)
    code = mock_send_email[-1]["body"].split()[4].rstrip(".")

    response = client.post("/v1/auth/verify-email", json={"code": code}, headers=headers)
    assert response.status_code == 200

    me = client.get("/v1/users/me", headers=headers)
    assert me.json()["email_verified"] is True

    today = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    assert today.status_code == 200


def test_verifying_again_after_already_verified_is_a_no_op(client, mock_send_email):
    headers = _register(client)
    code = mock_send_email[-1]["body"].split()[4].rstrip(".")
    client.post("/v1/auth/verify-email", json={"code": code}, headers=headers)

    response = client.post("/v1/auth/verify-email", json={"code": code}, headers=headers)
    assert response.status_code == 200


def test_wrong_code_is_rejected(client, mock_send_email):
    headers = _register(client)
    response = client.post("/v1/auth/verify-email", json={"code": "000000"}, headers=headers)
    assert response.status_code == 400


def test_lockout_after_five_wrong_attempts(client, mock_send_email):
    headers = _register(client)
    for _ in range(5):
        client.post("/v1/auth/verify-email", json={"code": "000000"}, headers=headers)

    response = client.post("/v1/auth/verify-email", json={"code": "000000"}, headers=headers)
    assert response.status_code == 429


def test_resend_immediately_after_register_is_rate_limited(client, mock_send_email):
    headers = _register(client)
    assert len(mock_send_email) == 1

    response = client.post("/v1/auth/resend-verification", headers=headers)
    assert response.status_code == 429
    assert len(mock_send_email) == 1


def test_resend_issues_a_new_code_once_cooldown_has_passed(client, mock_send_email):
    from app.db import verification_codes_table

    headers = _register(client)
    user_id = client.get("/v1/users/me", headers=headers).json()["user_id"]
    verification_codes_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET last_sent_epoch = :past",
        ExpressionAttributeValues={":past": 0},
    )

    response = client.post("/v1/auth/resend-verification", headers=headers)
    assert response.status_code == 200
    assert len(mock_send_email) == 2

    code = mock_send_email[-1]["body"].split()[4].rstrip(".")
    response = client.post("/v1/auth/verify-email", json={"code": code}, headers=headers)
    assert response.status_code == 200


def test_dev_login_is_auto_verified(client):
    response = client.post("/v1/auth/dev-login", json={"display_name": "Tom"})
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    me = client.get("/v1/users/me", headers=headers)
    assert me.json()["email_verified"] is True

    today = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    assert today.status_code == 200
