def test_dev_login_issues_usable_token(client):
    response = client.post("/v1/auth/dev-login", json={"display_name": "Tom"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]

    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Tom"


def test_refresh_issues_new_access_token(client):
    login = client.post("/v1/auth/dev-login", json={"display_name": "Tom"}).json()

    response = client.post("/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_protected_route_rejects_garbage_token(client):
    response = client.get("/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_register_then_login_with_password(client):
    register = client.post(
        "/v1/auth/register",
        json={"email": "Tom@Example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    assert register.status_code == 201

    login = client.post("/v1/auth/login", json={"email": "tom@example.com", "password": "correct-horse"})
    assert login.status_code == 200

    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["display_name"] == "Tom"


def test_register_assigns_a_random_avatar(client):
    from app.services.user_service import VALID_AVATAR_IDS

    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {register.json()['access_token']}"})
    assert me.json()["avatar_id"] in VALID_AVATAR_IDS


def test_register_assigns_a_random_avatar_color(client):
    from app.services.user_service import VALID_AVATAR_COLOR_IDS

    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {register.json()['access_token']}"})
    assert me.json()["avatar_color_id"] in VALID_AVATAR_COLOR_IDS


def test_register_rejects_duplicate_email(client):
    body = {"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"}
    assert client.post("/v1/auth/register", json=body).status_code == 201
    assert client.post("/v1/auth/register", json=body).status_code == 409


def test_login_rejects_wrong_password(client):
    client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    response = client.post("/v1/auth/login", json={"email": "tom@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert response.status_code == 401


def test_register_rejects_short_password(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "short", "display_name": "Tom"},
    )
    assert response.status_code == 422


def test_register_rejects_display_name_containing_at_sign(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom@Puzzles"},
    )
    assert response.status_code == 422


def test_register_rejects_duplicate_display_name_case_insensitive(client):
    client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse", "display_name": "Tom"},
    )
    response = client.post(
        "/v1/auth/register",
        json={"email": "other@example.com", "password": "correct-horse", "display_name": "TOM"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "display name already taken"
