def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"


def test_root_is_health(client):
    assert client.get("/").status_code == 200
