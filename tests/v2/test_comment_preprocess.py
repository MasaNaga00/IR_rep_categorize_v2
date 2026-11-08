"""R-64〜R-67: 修理者コメントの注記の除去(2026-11-08 追加)。"""
from __future__ import annotations

import json

import pytest

from repclass.comment_preprocess import (PreprocessConfigError, PreprocessRules, apply_preprocess,
                                         load_preprocess_rules, strip_notes)
from repclass.input_loader import load_input
from repclass.pipeline import run_pipeline

from .conftest import REPO_ROOT, read_csv

SQ = "\u25fe"          # ◾
SQ_E = "\u25fe\ufe0f"  # ◾️(絵文字の見た目を変える見えない文字つき)
STAR_E = "\u2b50\ufe0f"
KOME = "\u203b"        # ※
MARKERS = (SQ, "\u2b50", KOME)


# --- 設定ファイル(R-64) ---

def test_r64_repository_default_config():
    rules = load_preprocess_rules(REPO_ROOT / "config" / "comment_preprocess.yaml")
    assert rules.note_markers == ("\u25fe", "\u2b50", "\u203b", "\u25a0", "\u2605")
    assert rules.apply_repair_comment is True and rules.apply_user_comment is False
    assert rules.marker_codes() == ["U+25FE", "U+2B50", "U+203B", "U+25A0", "U+2605"]
    assert len(rules.sha256) == 64


def _cfg(tmp_path, text):
    p = tmp_path / "comment_preprocess.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_r64_escaped_markers_in_any_quote_style(tmp_path):
    """\\u の形は、ダブルクォート・シングルクォート・クォートなしのどれで書いても同じ文字になる。"""
    p = _cfg(tmp_path, 'note_markers:\n  - "\\u25A0"\n  - \'\\u2605\'\n  - \\u203B\n')
    assert load_preprocess_rules(p).note_markers == ("\u25a0", "\u2605", "\u203b")


def test_r64_variation_selector_in_marker_is_ignored(tmp_path):
    p = _cfg(tmp_path, 'note_markers:\n  - "\\u25FE\\uFE0F"\n')
    assert load_preprocess_rules(p).note_markers == ("\u25fe",)


@pytest.mark.parametrize("text, why", [
    ("note_markers: \"\\u25A0\"\n", "リストでない"),
    ("note_markers:\n  - \"\"\n", "空の文字列"),
    ("note_markers:\n  - \"\\uFE0F\"\n", "見えない文字だけ"),
    ("note_markers: []\napply_to:\n  repair_comment: yes_please\n", "apply_to が真偽値でない"),
    ("note_markers: []\nunknown_key: 1\n", "不明な項目"),
])
def test_r64_invalid_config(tmp_path, text, why):
    with pytest.raises(PreprocessConfigError):
        load_preprocess_rules(_cfg(tmp_path, text))


def test_r64_empty_markers_do_nothing(tmp_path):
    rules = load_preprocess_rules(_cfg(tmp_path, "note_markers: []\n"))
    assert rules.note_markers == ()
    assert strip_notes("清掃しました" + SQ + "ファーム更新", rules.note_markers) == ("清掃しました" + SQ + "ファーム更新", [])


# --- 取り除く範囲(R-65) ---

def test_r65_example3_all_notes_after_main_text():
    text = ("センサー表面を清掃いたしました" + SQ_E + "カメラのファームウエアを更新しました。" + SQ_E
            + "シャッター回数は約1,000回です。" + STAR_E + "バッテリーが劣化しております。")
    cleaned, notes = strip_notes(text, MARKERS)
    assert cleaned == "センサー表面を清掃いたしました"
    assert notes == ["カメラのファームウエアを更新しました。", "シャッター回数は約1,000回です。", "バッテリーが劣化しております。"]


def test_r65_stops_before_next_circled_number():
    text = "①センサーを清掃しました" + KOME + "作業に伴い設定を初期化しました②グリップラバーを交換しました。" + SQ + "回数は約15,000回です。"
    cleaned, notes = strip_notes(text, MARKERS)
    assert cleaned == "①センサーを清掃しました②グリップラバーを交換しました。"
    assert notes == ["作業に伴い設定を初期化しました", "回数は約15,000回です。"]


def test_r65_no_marker_unchanged():
    text = "電源基板を交換しました。 "
    assert strip_notes(text, MARKERS) == (text, [])
    assert strip_notes("", MARKERS) == ("", [])


def test_r65_marker_at_start_removes_until_circled():
    cleaned, notes = strip_notes(KOME + "ショック品①シャッターを交換しました", MARKERS)
    assert cleaned == "①シャッターを交換しました" and notes == ["ショック品"]


def test_r65_variation_selector_after_marker_in_text():
    cleaned, notes = strip_notes("清掃しました" + SQ + "\ufe0f" + "回数は1000回", (SQ,))
    assert cleaned == "清掃しました" and notes == ["回数は1000回"]


def test_r65_consecutive_markers_without_text():
    cleaned, notes = strip_notes("交換しました" + SQ + SQ + "回数は1000回", MARKERS)
    assert cleaned == "交換しました" and notes == ["回数は1000回"]


def test_r65_multi_character_marker():
    cleaned, notes = strip_notes("交換しました【備考】回数は1000回", ("【備考】",))
    assert cleaned == "交換しました" and notes == ["回数は1000回"]


# --- 対象(R-66)と記録(R-67) ---

def test_r66_r67_apply_to_records():
    recs = [
        {"repair_id": "A", "row_number": 1, "user_comment": "①AF" + SQ + "メモ", "repair_comment": "交換" + SQ + "回数"},
        {"repair_id": "B", "row_number": 2, "user_comment": "AF", "repair_comment": "交換しました"},
    ]
    rows = apply_preprocess(recs, PreprocessRules(note_markers=(SQ,)))
    a, b = recs
    assert a["repair_comment"] == "交換" and a["repair_comment_original"] == "交換" + SQ + "回数"
    assert a["repair_comment_notes"] == "回数"
    assert a["user_comment"] == "①AF" + SQ + "メモ" and a["user_comment_notes"] == ""   # 既定ではユーザコメントにかけない
    assert "repair_comment_original" not in b and b["repair_comment_notes"] == ""
    assert rows == [{"row_number": 1, "excel_row": 2, "repair_id": "A", "field": "repair_comment",
                     "removed": "回数", "remaining": "交換"}]


def test_r66_user_comment_when_enabled():
    recs = [{"repair_id": "A", "row_number": 1, "user_comment": "①AF" + SQ + "メモ②液晶", "repair_comment": "交換"}]
    apply_preprocess(recs, PreprocessRules(note_markers=(SQ,), apply_user_comment=True))
    assert recs[0]["user_comment"] == "①AF②液晶" and recs[0]["user_comment_notes"] == "メモ"


def test_r67_multiple_notes_joined():
    recs = [{"repair_id": "A", "row_number": 1, "user_comment": "", "repair_comment": "交換" + SQ + "回数" + SQ + "電池"}]
    apply_preprocess(recs, PreprocessRules(note_markers=(SQ,)))
    assert recs[0]["repair_comment_notes"] == "回数 | 電池"


# --- 実行全体(R-67) ---

@pytest.fixture
def rules():
    return load_preprocess_rules(REPO_ROOT / "config" / "comment_preprocess.yaml")


def _run(tmp_path, codebook, synth_csv, client, **kw):
    kw.setdefault("timestamp", "20261108_120000")
    return run_pipeline(synth_csv, codebook=codebook, client=client, output_dir=tmp_path / "out", **kw)


def test_r67_notes_are_not_sent_to_dify(tmp_path, codebook, synth_csv, fake_client_factory, rules):
    client = fake_client_factory()
    res = _run(tmp_path, codebook, synth_csv, client, preprocess=rules)
    sent = {r["repair_id"]: r for c in client.calls for r in json.loads(c["records"])}
    assert sent["T050"]["repair_comment"] == "センサー表面を清掃いたしました"
    assert sent["T051"]["repair_comment"] == "①センサー表面を清掃いたしました②グリップラバーの変色を確認したため、グリップラバーを交換いたしました。"
    assert "\u203b" not in sent["T001"]["repair_comment"]   # 付随作業の ※ も取り除く
    assert sent["T002"]["repair_comment"] == read_csv(synth_csv)[1]["repair_comment"]   # マークの無いものはそのまま
    # 抜き出しが取り除く前の文にある場合も警告にしない
    assert res.meta["counts"] == {"input": 58, "excluded": 2, "ok": 56, "warning": 0, "error": 0}


def test_r67_repairs_csv_and_removed_notes_file(tmp_path, codebook, synth_csv, fake_client_factory, rules):
    res = _run(tmp_path, codebook, synth_csv, fake_client_factory(), preprocess=rules)
    repairs = {r["repair_id"]: r for r in read_csv(res.run_dir / "repairs.csv")}
    orig = {r["ID"]: r for r in read_csv(synth_csv)}
    t050 = repairs["T050"]
    assert t050["repair_comment"] == orig["T050"]["repair_comment"]   # 入力どおりの全文
    assert t050["repair_comment_notes"] == ("カメラのファームウエアを最新のファームウエアに更新しました。 | "
                                            "現在のシャッター回数は約1,000回です。 | バッテリーが劣化しております。お買い替えをお勧めいたします。")
    assert repairs["T002"]["repair_comment_notes"] == ""
    assert "user_comment_notes" in t050
    rows = read_csv(res.run_dir / "removed_notes.csv")
    assert list(rows[0]) == ["row_number", "excel_row", "repair_id", "field", "removed", "remaining"]
    ids = [r["repair_id"] for r in rows]
    assert "T050" in ids and "T051" in ids and "T002" not in ids
    assert all(r["field"] == "repair_comment" for r in rows)
    meta = res.meta["preprocess"]
    assert meta["markers"] == ["U+25FE", "U+2B50", "U+203B", "U+25A0", "U+2605"]
    assert meta["repairs_with_notes"] == len(set(ids))
    assert meta["sha256"] == rules.sha256
    assert meta["apply_to"] == {"repair_comment": True, "user_comment": False}


def test_r67_dry_run_writes_removed_notes(tmp_path, codebook, synth_csv, rules):
    res = run_pipeline(synth_csv, codebook=codebook, client=None, output_dir=tmp_path / "out",
                       dry_run=True, timestamp="20261108_130000", preprocess=rules)
    rows = read_csv(res.run_dir / "removed_notes.csv")
    assert any(r["repair_id"] == "T050" and r["remaining"] == "センサー表面を清掃いたしました" for r in rows)
    req = json.loads(next((res.run_dir / "raw").glob("batch_004_request.json")).read_text(encoding="utf-8"))
    sent = {r["repair_id"]: r for r in json.loads(req["inputs"]["records"])}
    assert sent["T050"]["repair_comment"] == "センサー表面を清掃いたしました"


def test_r67_without_preprocess_nothing_removed(tmp_path, codebook, synth_csv, fake_client_factory):
    client = fake_client_factory()
    res = _run(tmp_path, codebook, synth_csv, client)
    sent = {r["repair_id"]: r for c in client.calls for r in json.loads(c["records"])}
    assert sent["T050"]["repair_comment"] == read_csv(synth_csv)[49]["repair_comment"]
    assert read_csv(res.run_dir / "removed_notes.csv") == []
    assert res.meta["preprocess"] is None


def test_r67_resume_keeps_preprocess(tmp_path, codebook, synth_csv, fake_client_factory, rules):
    first = _run(tmp_path, codebook, synth_csv, fake_client_factory(broken_ids={"T050"}), preprocess=rules)
    client = fake_client_factory()
    _run(tmp_path, codebook, synth_csv, client, resume_from=first.run_dir, timestamp="20261108_140000", preprocess=rules)
    sent = [r for c in client.calls for r in json.loads(c["records"])]
    assert [r["repair_id"] for r in sent] == ["T050"]
    assert sent[0]["repair_comment"] == "センサー表面を清掃いたしました"


# --- 実行コマンド(R-57、R-67) ---

def test_r67_cli_summary(tmp_path, monkeypatch, capsys):
    from repclass.local_config import init_local
    from repclass.run import main
    local = tmp_path / "local"
    init_local(local)
    assert (local / "comment_preprocess.yaml").exists()   # init でコピーされる
    monkeypatch.delenv("REPCLASS_LOCAL_DIR", raising=False)
    code = main(["--input", str(synth_csv_path()), "--local-dir", str(local),
                 "--codebook", str(REPO_ROOT / "tests" / "fixtures" / "codebook_test.yaml"), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "注記を取り除いた修理:" in out and "U+25FE" in out and "removed_notes.csv" in out
    assert len(out.splitlines()) <= 15


def test_r67_cli_warns_when_no_marker_matches(tmp_path, monkeypatch, capsys):
    from repclass.local_config import init_local
    from repclass.run import main
    local = tmp_path / "local"
    init_local(local)
    (local / "comment_preprocess.yaml").write_text('note_markers:\n  - "\\u2666"\n', encoding="utf-8")
    monkeypatch.delenv("REPCLASS_LOCAL_DIR", raising=False)
    main(["--input", str(synth_csv_path()), "--local-dir", str(local),
          "--codebook", str(REPO_ROOT / "tests" / "fixtures" / "codebook_test.yaml"), "--dry-run"])
    out = capsys.readouterr().out
    assert "注記を取り除いた修理: 0 件" in out
    assert "comment_preprocess.yaml" in out   # マークの文字が合っていない可能性の案内


def test_r67_cli_invalid_config(tmp_path, monkeypatch, capsys):
    from repclass.local_config import init_local
    from repclass.run import main
    local = tmp_path / "local"
    init_local(local)
    (local / "comment_preprocess.yaml").write_text("note_markers: 1\n", encoding="utf-8")
    monkeypatch.delenv("REPCLASS_LOCAL_DIR", raising=False)
    code = main(["--input", str(synth_csv_path()), "--local-dir", str(local), "--dry-run"])
    assert code == 2
    assert "comment_preprocess.yaml" in capsys.readouterr().out


def synth_csv_path():
    from .conftest import SYNTH
    return SYNTH / "repairs.csv"


def test_r67_input_loader_unchanged(codebook, synth_csv):
    """読み込みの段階では取り除かない(実行全体の中で取り除く)。"""
    recs = {r["repair_id"]: r for r in load_input(synth_csv, codebook).records}
    assert "\u25fe" in recs["T050"]["repair_comment"]
