"""R-52, R-53: Dify ワークフロー API の呼び出し(通信はモック)。"""
from __future__ import annotations

import pytest
import requests

from repclass.dify_client import DifyAPIError, DifyClient, DifyResponse

BASE = "https://dify.example.local/v1"
URL = BASE + "/workflows/run"


def _ok(text='{"results": []}', tokens=321):
    return {"json": {"workflow_run_id": "w1", "data": {"status": "succeeded", "outputs": {"result": text}, "total_tokens": tokens, "error": None}}, "status_code": 200}


@pytest.fixture
def client():
    return DifyClient(BASE, "app-test", timeout=5, max_retries=3, backoff=0)


def test_r52_success(requests_mock, client):
    requests_mock.post(URL, **_ok('{"results": [1]}'))
    r = client.run({"product_name": "x", "code_list": "y", "records": "[]"})
    assert isinstance(r, DifyResponse)
    assert r.text == '{"results": [1]}' and r.total_tokens == 321
    req = requests_mock.request_history[0]
    assert req.headers["Authorization"] == "Bearer app-test"
    body = req.json()
    assert body["inputs"] == {"product_name": "x", "code_list": "y", "records": "[]"}
    assert body["response_mode"] == "blocking"
    assert body["user"]


def test_r52_trailing_slash_in_base_url(requests_mock):
    requests_mock.post(URL, **_ok())
    DifyClient(BASE + "/", "app-test", backoff=0).run({})
    assert requests_mock.call_count == 1


def test_r53_retry_on_5xx_then_success(requests_mock, client):
    requests_mock.post(URL, [{"status_code": 502, "text": "bad gateway"}, {"status_code": 500, "text": "err"}, _ok()])
    assert client.run({}).text == '{"results": []}'
    assert requests_mock.call_count == 3


def test_r53_retry_on_timeout(requests_mock, client):
    requests_mock.post(URL, [{"exc": requests.exceptions.ConnectTimeout}, _ok()])
    client.run({})
    assert requests_mock.call_count == 2


def test_r53_gives_up_after_max_retries(requests_mock, client):
    requests_mock.post(URL, status_code=503, text="unavailable")
    with pytest.raises(DifyAPIError) as ei:
        client.run({})
    assert ei.value.status_code == 503
    assert requests_mock.call_count == 4   # 初回 + 3回リトライ


@pytest.mark.parametrize("code", [401, 403])
def test_r53_no_retry_on_auth_error(requests_mock, client, code):
    requests_mock.post(URL, status_code=code, text="unauthorized")
    with pytest.raises(DifyAPIError) as ei:
        client.run({})
    assert ei.value.status_code == code
    assert requests_mock.call_count == 1


def test_r53_workflow_failed_status(requests_mock, client):
    requests_mock.post(URL, json={"data": {"status": "failed", "outputs": None, "error": "LLM error"}}, status_code=200)
    with pytest.raises(DifyAPIError) as ei:
        client.run({})
    assert "LLM error" in str(ei.value)


def test_r52_from_env(monkeypatch):
    monkeypatch.setenv("DIFY_BASE_URL", BASE)
    monkeypatch.setenv("DIFY_API_KEY", "app-env")
    c = DifyClient.from_env()
    assert c.base_url == BASE and c.api_key == "app-env"


def test_r52_from_env_missing(monkeypatch):
    monkeypatch.delenv("DIFY_BASE_URL", raising=False)
    monkeypatch.delenv("DIFY_API_KEY", raising=False)
    with pytest.raises(ValueError):
        DifyClient.from_env(env_file=None)
