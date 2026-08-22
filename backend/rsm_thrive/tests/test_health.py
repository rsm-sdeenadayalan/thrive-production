def test_health(client):
    resp = client.get("/api/thrive/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
