def _mock_google_claims(monkeypatch, claims: dict) -> None:
    monkeypatch.setattr("app.services.auth_service.verify_google_id_token", lambda token: claims)


def test_google_sign_in_creates_a_verified_user(client, monkeypatch):
    _mock_google_claims(monkeypatch, {"sub": "google-123", "email": "gina@example.com", "name": "Gina"})

    response = client.post("/v1/auth/google", json={"id_token": "fake"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    me = client.get("/v1/users/me", headers=headers)
    assert me.json()["email_verified"] is True

    today = client.get("/v1/puzzles/today", params={"game": "boggle"}, headers=headers)
    assert today.status_code == 200


def test_google_sign_in_fixes_a_previously_unverified_account(client, monkeypatch):
    from app.services.user_service import create_user_with_identity

    # Simulates an account created before email verification existed (or missed by the
    # one-off backfill) -- it should never be stuck unverified just because it predates
    # the feature, since Google already independently verified this email.
    create_user_with_identity(
        provider="google",
        provider_subject="google-456",
        display_name="Legacy",
        email="legacy@example.com",
        email_verified=False,
    )

    _mock_google_claims(monkeypatch, {"sub": "google-456", "email": "legacy@example.com", "name": "Legacy"})

    response = client.post("/v1/auth/google", json={"id_token": "fake"})
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    me = client.get("/v1/users/me", headers=headers)
    assert me.json()["email_verified"] is True
