def _user_id(client, headers):
    return client.get("/v1/users/me", headers=headers).json()["user_id"]


def test_send_request_then_accept_creates_mutual_friendship(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)
    tom_id = _user_id(client, tom)

    response = client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    assert response.status_code == 201

    response = client.post(f"/v1/friends/requests/{tom_id}/accept", headers=alex)
    assert response.status_code == 200

    tom_friends = client.get("/v1/friends", headers=tom).json()
    alex_friends = client.get("/v1/friends", headers=alex).json()
    assert [f["user_id"] for f in tom_friends] == [alex_id]
    assert [f["user_id"] for f in alex_friends] == [tom_id]


def test_cannot_send_friend_request_to_self(client, auth_headers):
    tom = auth_headers("Tom")
    tom_id = _user_id(client, tom)
    response = client.post("/v1/friends/requests", json={"to_user_id": tom_id}, headers=tom)
    assert response.status_code == 400


def test_mutual_pending_requests_auto_accept(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)
    tom_id = _user_id(client, tom)

    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    response = client.post("/v1/friends/requests", json={"to_user_id": tom_id}, headers=alex)
    assert response.status_code == 201

    assert [f["user_id"] for f in client.get("/v1/friends", headers=tom).json()] == [alex_id]
    assert [f["user_id"] for f in client.get("/v1/friends", headers=alex).json()] == [tom_id]
    assert client.get("/v1/friends/requests/incoming", headers=tom).json() == []
    assert client.get("/v1/friends/requests/incoming", headers=alex).json() == []


def test_duplicate_friend_request_rejected(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)

    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    response = client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    assert response.status_code == 409


def test_decline_request_removes_it_without_creating_friendship(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)
    tom_id = _user_id(client, tom)

    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    response = client.post(f"/v1/friends/requests/{tom_id}/decline", headers=alex)
    assert response.status_code == 200
    assert client.get("/v1/friends", headers=tom).json() == []
    assert client.get("/v1/friends", headers=alex).json() == []


def test_unfriend_removes_both_directions(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)
    tom_id = _user_id(client, tom)

    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)
    client.post(f"/v1/friends/requests/{tom_id}/accept", headers=alex)

    response = client.delete(f"/v1/friends/{alex_id}", headers=tom)
    assert response.status_code == 200
    assert client.get("/v1/friends", headers=tom).json() == []
    assert client.get("/v1/friends", headers=alex).json() == []


def test_search_by_exact_email_finds_user(client, auth_headers):
    tom = auth_headers("Tom")
    response = client.post(
        "/v1/auth/register",
        json={"email": "alex@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    alex_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    alex_name = client.get("/v1/users/me", headers=alex_headers).json()["display_name"]

    results = client.get("/v1/users/search", params={"q": "alex@example.com"}, headers=tom).json()
    assert len(results) == 1
    assert results[0]["display_name"] == alex_name
    assert results[0]["friendship_status"] == "none"


def test_search_by_partial_display_name_is_case_insensitive(client, auth_headers):
    tom = auth_headers("Tom")
    auth_headers("Alexandra")

    results = client.get("/v1/users/search", params={"q": "LEX"}, headers=tom).json()
    assert any(r["display_name"] == "Alexandra" for r in results)


def test_search_excludes_self(client, auth_headers):
    tom = auth_headers("Tom")
    results = client.get("/v1/users/search", params={"q": "tom"}, headers=tom).json()
    assert all(r["display_name"] != "Tom" for r in results)


def test_search_result_reports_existing_friendship_status(client, auth_headers):
    tom = auth_headers("Tom")
    alex = auth_headers("Alex")
    alex_id = _user_id(client, alex)

    client.post("/v1/friends/requests", json={"to_user_id": alex_id}, headers=tom)

    results = client.get("/v1/users/search", params={"q": "alex"}, headers=tom).json()
    assert next(r["friendship_status"] for r in results if r["user_id"] == alex_id) == "request_sent"


def test_friends_endpoints_require_auth(client):
    assert client.get("/v1/friends").status_code == 401
    assert client.get("/v1/friends/requests/incoming").status_code == 401
    assert client.get("/v1/friends/requests/outgoing").status_code == 401
    assert client.get("/v1/users/search", params={"q": "a"}).status_code == 401
    assert client.post("/v1/friends/requests", json={"to_user_id": "u_1"}).status_code == 401
