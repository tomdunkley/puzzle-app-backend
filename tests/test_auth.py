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
        json={"email": "Tom@Example.com", "password": "correct-horse"},
    )
    assert register.status_code == 201

    login = client.post("/v1/auth/login", json={"email": "tom@example.com", "password": "correct-horse"})
    assert login.status_code == 200

    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    name = me.json()["display_name"]
    assert name[0].isupper() and name[-1].isdigit()  # auto-generated AdjectiveNoun## format


def test_register_assigns_a_random_avatar(client):
    from app.services.user_service import VALID_AVATAR_IDS

    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse"},
    )
    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {register.json()['access_token']}"})
    assert me.json()["avatar_id"] in VALID_AVATAR_IDS


def test_register_assigns_a_random_avatar_color(client):
    from app.services.user_service import VALID_AVATAR_COLOR_IDS

    register = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse"},
    )
    me = client.get("/v1/users/me", headers={"Authorization": f"Bearer {register.json()['access_token']}"})
    assert me.json()["avatar_color_id"] in VALID_AVATAR_COLOR_IDS


def test_register_rejects_duplicate_email(client):
    body = {"email": "tom@example.com", "password": "correct-horse"}
    assert client.post("/v1/auth/register", json=body).status_code == 201
    assert client.post("/v1/auth/register", json=body).status_code == 409


def test_login_rejects_wrong_password(client):
    client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "correct-horse"},
    )
    response = client.post("/v1/auth/login", json={"email": "tom@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert response.status_code == 401


def test_register_rejects_short_password(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "tom@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_register_generates_auto_display_names(client):
    r1 = client.post("/v1/auth/register", json={"email": "a@example.com", "password": "correct-horse"})
    r2 = client.post("/v1/auth/register", json={"email": "b@example.com", "password": "correct-horse"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    me1 = client.get("/v1/users/me", headers={"Authorization": f"Bearer {r1.json()['access_token']}"}).json()
    me2 = client.get("/v1/users/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"}).json()
    assert me1["display_name"] != me2["display_name"]
    # Names follow the AdjectiveNoun## format
    assert me1["display_name"][0].isupper() and me1["display_name"][-1].isdigit()
