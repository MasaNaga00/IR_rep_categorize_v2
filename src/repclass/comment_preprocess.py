"""R-64〜R-67: 修理者コメントの注記の除去(2026-11-08 追加)。

修理者コメントの後ろに決まったマーク(◾️・⭐️・※ など)で書かれる、修理と関係のない注記を、
Dify に渡す前に取り除く。取り除く範囲は、マークから「次のマーク・次の丸数字・コメントの終わり」の
うち最初に来るところの手前まで(R-65)。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

VARIATION_SELECTORS = frozenset({"︎", "️"})   # 絵文字の見た目を変える見えない文字
CIRCLED_NUMBERS = frozenset(chr(c) for c in range(0x2460, 0x2474))   # ①〜⑳
NOTE_SEP = " | "
FIELDS = ("user_comment", "repair_comment")
REMOVED_COLUMNS = ["row_number", "excel_row", "repair_id", "field", "removed", "remaining"]
_ESCAPED = re.compile(r"\\u([0-9A-Fa-f]{4})")


class PreprocessConfigError(ValueError):
    """comment_preprocess.yaml の内容の誤り。"""


@dataclass(frozen=True)
class PreprocessRules:
    note_markers: tuple[str, ...] = ()
    apply_repair_comment: bool = True
    apply_user_comment: bool = False
    path: Path | None = None
    sha256: str | None = None

    def marker_codes(self) -> list[str]:
        """マークを U+25FE の形で返す(実行メタ情報・要約の表示用)。"""
        return [" ".join(f"U+{ord(ch):04X}" for ch in m) for m in self.note_markers]

    def applies_to(self, field: str) -> bool:
        return self.apply_repair_comment if field == "repair_comment" else self.apply_user_comment


def _drop_vs(s: str) -> str:
    return "".join(ch for ch in s if ch not in VARIATION_SELECTORS)


def _decode_marker(v) -> str:
    # シングルクォート・クォートなしで書かれた ■ も文字に直す
    return _drop_vs(_ESCAPED.sub(lambda m: chr(int(m.group(1), 16)), str(v)))


def load_preprocess_rules(path: str | Path) -> PreprocessRules:
    p = Path(path)
    raw = p.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise PreprocessConfigError(f"{p}: 中身が辞書の形ではありません")
    unknown = set(data) - {"note_markers", "apply_to"}
    if unknown:
        raise PreprocessConfigError(f"{p}: 不明な項目があります: {', '.join(sorted(unknown))}")
    markers_raw = data.get("note_markers") or []
    if not isinstance(markers_raw, list):
        raise PreprocessConfigError(f"{p}: note_markers はリスト(- で始まる行)にしてください")
    markers: list[str] = []
    for i, v in enumerate(markers_raw, start=1):
        m = _decode_marker(v) if v is not None else ""
        if not m:
            raise PreprocessConfigError(f"{p}: note_markers の {i} 番目が空です")
        if m not in markers:
            markers.append(m)
    apply_to = data.get("apply_to") or {}
    if not isinstance(apply_to, dict) or set(apply_to) - set(FIELDS):
        raise PreprocessConfigError(f"{p}: apply_to には repair_comment / user_comment だけを書いてください")
    flags = {}
    for k, default in (("repair_comment", True), ("user_comment", False)):
        v = apply_to.get(k, default)
        if not isinstance(v, bool):
            raise PreprocessConfigError(f"{p}: apply_to.{k} は true / false にしてください")
        flags[k] = v
    return PreprocessRules(tuple(markers), flags["repair_comment"], flags["user_comment"], p,
                           hashlib.sha256(raw).hexdigest())


def strip_notes(text: str, markers) -> tuple[str, list[str]]:
    """注記を取り除いた文と、取り除いた注記(マークを除く)のリストを返す。マークが無ければ text をそのまま返す。"""
    marks = [m for m in (_drop_vs(x) for x in markers) if m]
    if not text or not marks:
        return text, []

    def marker_at(j: int) -> str | None:
        return next((m for m in marks if text.startswith(m, j)), None)

    kept: list[str] = []
    notes: list[str] = []
    found = False
    i = seg = 0
    n = len(text)
    while i < n:
        m = marker_at(i)
        if m is None:
            i += 1
            continue
        found = True
        kept.append(text[seg:i])
        j = i + len(m)
        while j < n and text[j] not in CIRCLED_NUMBERS and marker_at(j) is None:
            j += 1
        note = _drop_vs(text[i + len(m):j]).strip()
        if note:
            notes.append(note)
        i = seg = j
    if not found:
        return text, []
    kept.append(text[seg:])
    return "".join(kept).rstrip(), notes


def apply_preprocess(records: list[dict], rules: PreprocessRules) -> list[dict]:
    """records を書き換える(取り除いた後の文を user_comment / repair_comment に、元の文を *_original に、
    注記を *_notes に入れる)。removed_notes.csv の行のリストを返す。"""
    rows: list[dict] = []
    for rec in records:
        for field in FIELDS:
            rec[f"{field}_notes"] = ""
            if not rules.applies_to(field):
                continue
            original = rec.get(field) or ""
            cleaned, notes = strip_notes(original, rules.note_markers)
            if cleaned == original:
                continue
            rec[f"{field}_original"] = original
            rec[field] = cleaned
            rec[f"{field}_notes"] = NOTE_SEP.join(notes)
            rn = rec.get("row_number")
            rows.append({"row_number": rn, "excel_row": rn + 1 if isinstance(rn, int) else "",
                         "repair_id": rec.get("repair_id", ""), "field": field,
                         "removed": NOTE_SEP.join(notes), "remaining": cleaned})
    return rows
