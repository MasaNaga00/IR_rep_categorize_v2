"""R-05a, R-49: ローカル作業フォルダと実行コマンド。"""
from __future__ import annotations

from pathlib import Path

from repclass.local_config import init_local, resolve_paths

from .conftest import REPO_ROOT, SYNTH


def test_r05a_defaults_without_local_dir(monkeypatch):
    monkeypatch.delenv("REPCLASS_LOCAL_DIR", raising=False)
    p = resolve_paths()
    assert p.codebook == REPO_ROOT / "config" / "classification_codes.yaml"
    assert p.columns == REPO_ROOT / "config" / "input_columns.yaml"
    assert p.prompt == REPO_ROOT / "config" / "prompts" / "v2" / "system_prompt.md"
    assert p.outputs_dir == REPO_ROOT / "outputs" / "v2"
    assert p.env_file == REPO_ROOT / ".env"


def test_r05a_init_local_copies_without_overwrite(tmp_path):
    local = tmp_path / "local"
    created = init_local(local)
    for rel in ("classification_codes.yaml", "input_columns.yaml", "prompts/system_prompt.md",
                ".env", "eval_name_map.csv", "data", "outputs"):
        assert (local / rel).exists(), rel
    assert len(created) >= 7
    (local / "classification_codes.yaml").write_text("# edited", encoding="utf-8")
    created2 = init_local(local)
    assert created2 == []
    assert (local / "classification_codes.yaml").read_text(encoding="utf-8") == "# edited"


def test_r05a_resolution_order(tmp_path, monkeypatch):
    local = tmp_path / "local"
    init_local(local)
    monkeypatch.setenv("REPCLASS_LOCAL_DIR", str(local))
    p = resolve_paths()
    assert p.codebook == local / "classification_codes.yaml"
    assert p.outputs_dir == local / "outputs"
    assert p.env_file == local / ".env"
    explicit = tmp_path / "x.yaml"
    assert resolve_paths(codebook=explicit).codebook == explicit
    (local / "input_columns.yaml").unlink()
    assert resolve_paths().columns == REPO_ROOT / "config" / "input_columns.yaml"


def test_r49_cli_dry_run(tmp_path, monkeypatch, capsys):
    from repclass.run import main
    local = tmp_path / "local"
    init_local(local)
    monkeypatch.delenv("REPCLASS_LOCAL_DIR", raising=False)
    code = main(["--input", str(SYNTH / "repairs.csv"), "--local-dir", str(local),
                 "--codebook", str(REPO_ROOT / "tests" / "fixtures" / "codebook_test.yaml"), "--dry-run"])
    assert code == 0
    runs = list((local / "outputs").iterdir())
    assert len(runs) == 1 and (runs[0] / "raw" / "batch_001_request.json").exists()
    out = capsys.readouterr().out
    assert len(out.splitlines()) <= 15   # R-57 要約は短く


def test_r49_cli_with_injected_client(tmp_path, fake_client_factory, capsys):
    from repclass.run import main
    local = tmp_path / "local"
    init_local(local)
    code = main(["--input", str(SYNTH / "repairs.csv"), "--local-dir", str(local),
                 "--codebook", str(REPO_ROOT / "tests" / "fixtures" / "codebook_test.yaml")],
                client=fake_client_factory())
    assert code == 0
    out = capsys.readouterr().out
    assert "ok" in out and "error" in out
