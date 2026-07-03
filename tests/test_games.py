def test_list_games_includes_boggle(client):
    response = client.get("/v1/games")
    assert response.status_code == 200
    games = response.json()
    assert any(g["game"] == "boggle" for g in games)
