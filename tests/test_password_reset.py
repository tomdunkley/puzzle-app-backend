def _register(client, email="tom@example.com", password="correct-horse", display_name="Tom"):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert response.status_code == 201, response.text


def test_forgot_password_sends_a_code_for_a_registered_email(client, mock_send_email):
    _register(client)
    response = client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})
    assert response.status_code == 200
    assert len(mock_send_email) == 2  # the register code, then the reset code
    assert mock_send_email[-1]["to_address"] == "tom@example.com"


def test_forgot_password_is_a_silent_no_op_for_an_unknown_email(client, mock_send_email):
    response = client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert len(mock_send_email) == 0


def test_correct_code_resets_the_password(client, mock_send_email):
    _register(client)
    client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})
    code = mock_send_email[-1]["body"].split()[5].rstrip(".")

    response = client.post(
        "/v1/auth/reset-password",
        json={"email": "tom@example.com", "code": code, "new_password": "new-password-123"},
    )
    assert response.status_code == 200

    old_login = client.post(
        "/v1/auth/login", json={"email": "tom@example.com", "password": "correct-horse"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/v1/auth/login", json={"email": "tom@example.com", "password": "new-password-123"}
    )
    assert new_login.status_code == 200


def test_wrong_code_is_rejected(client, mock_send_email):
    _register(client)
    client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})

    response = client.post(
        "/v1/auth/reset-password",
        json={"email": "tom@example.com", "code": "000000", "new_password": "new-password-123"},
    )
    assert response.status_code == 400


def test_reset_with_unknown_email_is_rejected_without_revealing_that(client, mock_send_email):
    response = client.post(
        "/v1/auth/reset-password",
        json={
            "email": "nobody@example.com",
            "code": "000000",
            "new_password": "new-password-123",
        },
    )
    assert response.status_code == 400


def test_lockout_after_five_wrong_attempts(client, mock_send_email):
    _register(client)
    client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})

    for _ in range(5):
        client.post(
            "/v1/auth/reset-password",
            json={
                "email": "tom@example.com",
                "code": "000000",
                "new_password": "new-password-123",
            },
        )

    response = client.post(
        "/v1/auth/reset-password",
        json={"email": "tom@example.com", "code": "000000", "new_password": "new-password-123"},
    )
    assert response.status_code == 429


def test_resend_immediately_is_rate_limited(client, mock_send_email):
    _register(client)
    client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})
    assert len(mock_send_email) == 2

    response = client.post("/v1/auth/resend-password-reset", json={"email": "tom@example.com"})
    assert response.status_code == 429
    assert len(mock_send_email) == 2


def test_resend_issues_a_new_code_once_cooldown_has_passed(client, mock_send_email):
    from app.db import password_reset_codes_table

    _register(client)
    client.post("/v1/auth/forgot-password", json={"email": "tom@example.com"})
    me = client.post(
        "/v1/auth/login", json={"email": "tom@example.com", "password": "correct-horse"}
    )
    headers = {"Authorization": f"Bearer {me.json()['access_token']}"}
    user_id = client.get("/v1/users/me", headers=headers).json()["user_id"]

    password_reset_codes_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET last_sent_epoch = :past",
        ExpressionAttributeValues={":past": 0},
    )

    response = client.post("/v1/auth/resend-password-reset", json={"email": "tom@example.com"})
    assert response.status_code == 200
    assert len(mock_send_email) == 3

    code = mock_send_email[-1]["body"].split()[5].rstrip(".")
    response = client.post(
        "/v1/auth/reset-password",
        json={"email": "tom@example.com", "code": code, "new_password": "new-password-123"},
    )
    assert response.status_code == 200
