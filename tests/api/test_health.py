import requests

TIMEOUT = (2, 3)  # 连接超时、读取超时，单位：秒


def test_health_returns_200(api_base_url):
    response = requests.get(f"{api_base_url}/health", timeout=TIMEOUT, allow_redirects=False)
    assert response.status_code == 200, response.text


def test_health_returns_expected_json(api_base_url):
    response = requests.get(f"{api_base_url}/health", timeout=TIMEOUT, allow_redirects=False)
    assert response.status_code == 200, response.text
    assert response.headers.get("Content-Type", "").startswith("application/json")
    assert response.json() == {"status": "ok"}, response.text


def test_unknown_route_returns_404(api_base_url):
    response = requests.get(f"{api_base_url}/does-not-exist", timeout=TIMEOUT, allow_redirects=False)
    assert response.status_code == 404, response.text
