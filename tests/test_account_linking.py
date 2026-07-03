def _mock_google_claims(monkeypatch, claims: dict) -> None:
    monkeypatch.setattr("app.services.auth_service.verify_google_id_token", lambda token: claims)


def _google_sign_in(client, monkeypatch, sub: str, email: str, name: str = "Gina") -> dict:
    _mock_google_claims(monkeypatch, {"sub": sub, "email": email, "name": name})
    response = client.post("/v1/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_profile_reports_has_password_and_has_google(client, monkeypatch):
    headers = _google_sign_in(client, monkeypatch, sub="g-1", email="gina@example.com")
    me = client.get("/v1/users/me", headers=headers).json()
    assert me["has_google"] is True
    assert me["has_password"] is False


def test_google_user_can_set_up_a_password(client, monkeypatch):
    headers = _google_sign_in(client, monkeypatch, sub="g-2", email="gina2@example.com")

    response = client.post("/v1/auth/set-password", json={"new_password": "a-new-password"}, headers=headers)
    assert response.status_code == 200

    me = client.get("/v1/users/me", headers=headers).json()
    assert me["has_password"] is True

    login = client.post("/v1/auth/login", json={"email": "gina2@example.com", "password": "a-new-password"})
    assert login.status_code == 200


def test_setting_password_twice_is_rejected(client, monkeypatch):
    headers = _google_sign_in(client, monkeypatch, sub="g-3", email="gina3@example.com")
    client.post("/v1/auth/set-password", json={"new_password": "a-new-password"}, headers=headers)

    response = client.post("/v1/auth/set-password", json={"new_password": "another-password"}, headers=headers)
    assert response.status_code == 409


def test_password_user_can_change_password(client):
    register = client.post(
        "/v1/auth/register",
        json={"email": "changeme@example.com", "password": "correct-horse", "display_name": "Changer"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = client.post(
        "/v1/auth/change-password",
        json={"current_password": "correct-horse", "new_password": "a-new-password"},
        headers=headers,
    )
    assert response.status_code == 200

    old_login = client.post("/v1/auth/login", json={"email": "changeme@example.com", "password": "correct-horse"})
    assert old_login.status_code == 401

    new_login = client.post("/v1/auth/login", json={"email": "changeme@example.com", "password": "a-new-password"})
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client):
    register = client.post(
        "/v1/auth/register",
        json={"email": "changeme2@example.com", "password": "correct-horse", "display_name": "Changer2"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = client.post(
        "/v1/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "a-new-password"},
        headers=headers,
    )
    assert response.status_code == 401


def test_change_password_rejected_for_google_only_account(client, monkeypatch):
    headers = _google_sign_in(client, monkeypatch, sub="g-9", email="gina9@example.com")

    response = client.post(
        "/v1/auth/change-password",
        json={"current_password": "anything", "new_password": "a-new-password"},
        headers=headers,
    )
    assert response.status_code == 400


def test_google_sign_in_rejects_email_already_used_by_a_password_account(client, monkeypatch):
    """A fresh Google sign-in must never create a second, disconnected account that
    happens to share an email with an existing password account -- that email is
    already taken, full stop. (Linking Google to the *existing* account, via
    /v1/auth/link-google while signed in, is the correct way to get both.)
    """
    client.post(
        "/v1/auth/register",
        json={"email": "taken@example.com", "password": "correct-horse", "display_name": "Taken"},
    )
    _mock_google_claims(monkeypatch, {"sub": "g-4", "email": "taken@example.com", "name": "Gina"})
    response = client.post("/v1/auth/google", json={"id_token": "fake"})
    assert response.status_code == 409


def test_register_rejects_email_already_used_by_a_google_account(client, monkeypatch):
    _google_sign_in(client, monkeypatch, sub="g-8", email="gina8@example.com")

    response = client.post(
        "/v1/auth/register",
        json={"email": "gina8@example.com", "password": "correct-horse", "display_name": "Imposter"},
    )
    assert response.status_code == 409


def test_password_user_can_link_a_google_account(client, monkeypatch):
    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    _mock_google_claims(monkeypatch, {"sub": "g-5", "email": "tom@example.com", "name": "Tom"})
    response = client.post("/v1/auth/link-google", json={"id_token": "fake"}, headers=headers)
    assert response.status_code == 200

    me = client.get("/v1/users/me", headers=headers).json()
    assert me["has_google"] is True
    assert me["email_verified"] is True  # linking confirms the email via Google

    google_login = _google_sign_in(client, monkeypatch, sub="g-5", email="tom@example.com")
    same_user = client.get("/v1/users/me", headers=google_login).json()
    assert same_user["user_id"] == me["user_id"]


def test_link_google_rejects_mismatched_email(client, monkeypatch):
    register = client.post(
        "/v1/auth/register",
        json={"email": "tom2@example.com", "password": "correct-horse", "display_name": "Tom2"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    _mock_google_claims(monkeypatch, {"sub": "g-6", "email": "someoneelse@example.com", "name": "Someone"})
    response = client.post("/v1/auth/link-google", json={"id_token": "fake"}, headers=headers)
    assert response.status_code == 400


def test_link_google_rejects_an_already_linked_google_identity(client, monkeypatch):
    _google_sign_in(client, monkeypatch, sub="g-7", email="shared@example.com")

    register = client.post(
        "/v1/auth/register",
        json={"email": "tom3@example.com", "password": "correct-horse", "display_name": "Tom3"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    _mock_google_claims(monkeypatch, {"sub": "g-7", "email": "tom3@example.com", "name": "Tom3"})
    response = client.post("/v1/auth/link-google", json={"id_token": "fake"}, headers=headers)
    assert response.status_code == 409
