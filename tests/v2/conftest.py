"""v2(repclass)テストの共通設定。

- 実データ用の YAML には依存せず、tests/fixtures/codebook_test.yaml を使う(R-05)。
- 架空データは tests/fixtures/synthetic/ を使う(README.md 参照)。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = REPO_ROOT / "tests" / "fixtures"
SYNTH = FIXTURES / "synthetic"
CODEBOOK_TEST_YAML = FIXTURES / "codebook_test.yaml"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def codebook_path() -> Path:
    return CODEBOOK_TEST_YAML


@pytest.fixture(scope="session")
def codebook():
    from repclass.codebook import load_codebook
    return load_codebook(CODEBOOK_TEST_YAML)


@pytest.fixture(scope="session")
def synth_csv() -> Path:
    return SYNTH / "repairs.csv"


@pytest.fixture(scope="session")
def mock_results() -> dict:
    """架空データに対する理想的な LLM 応答(repair_id → 1修理分の結果)。"""
    return json.loads((SYNTH / "mock_llm_results.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def expected_final() -> dict:
    return {r["repair_id"]: r for r in read_csv(SYNTH / "expected_final.csv")}


@pytest.fixture(scope="session")
def expected_claims() -> list[dict]:
    return read_csv(SYNTH / "expected_claims.csv")


@pytest.fixture(scope="session")
def expected_environments() -> list[dict]:
    return read_csv(SYNTH / "expected_environments.csv")


@pytest.fixture(scope="session")
def expected_excluded() -> list[dict]:
    return read_csv(SYNTH / "expected_excluded.csv")


class FakeDifyClient:
    """Dify の代わりに mock_llm_results から応答を返すクライアント。

    - fail_batches: この回数目(1始まり)の呼び出しで DifyAPIError を送出
    - broken_ids: この repair_id を含む呼び出しでは、その修理の結果を壊す(未知コード)
    - broken_once_ids: この repair_id は最初の1回だけ壊し、再試行では正しく返す
    - invalid_json_calls: この回数目の呼び出しでは JSON として読めない文字列を返す
    """

    def __init__(self, results: dict, fail_batches=(), broken_ids=(), broken_once_ids=(), invalid_json_calls=()):
        self.results = results
        self.fail_batches = set(fail_batches)
        self.broken_ids = set(broken_ids)
        self.broken_once_ids = set(broken_once_ids)
        self.invalid_json_calls = set(invalid_json_calls)
        self.calls: list[dict] = []
        self._seen_once: set[str] = set()

    def run(self, inputs: dict):
        from repclass.dify_client import DifyAPIError, DifyResponse
        self.calls.append(inputs)
        n = len(self.calls)
        if n in self.fail_batches:
            raise DifyAPIError(500, "simulated server error")
        if n in self.invalid_json_calls:
            return DifyResponse(text="これはJSONではありません", total_tokens=10, raw={})
        recs = json.loads(inputs["records"])
        out = []
        for r in recs:
            rid = r["repair_id"]
            res = json.loads(json.dumps(self.results[rid]))
            broken = rid in self.broken_ids or (rid in self.broken_once_ids and rid not in self._seen_once)
            if rid in self.broken_once_ids:
                self._seen_once.add(rid)
            if broken:
                res["claims"][0]["user_code"] = "ZZZ999"
            out.append(res)
        return DifyResponse(text=json.dumps({"results": out}, ensure_ascii=False), total_tokens=100, raw={})


@pytest.fixture
def fake_client_factory(mock_results):
    def make(**kw):
        return FakeDifyClient(mock_results, **kw)
    return make
