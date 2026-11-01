"""R-05a: ローカル作業フォルダ(Windows 側で変更するファイルの置き場所)。"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_VAR = "REPCLASS_LOCAL_DIR"

# ローカル作業フォルダ内の相対パス → リポジトリの初期値
DEFAULTS = {
    "classification_codes.yaml": REPO_ROOT / "config" / "classification_codes.yaml",
    "input_columns.yaml": REPO_ROOT / "config" / "input_columns.yaml",
    "prompts/system_prompt.md": REPO_ROOT / "config" / "prompts" / "v2" / "system_prompt.md",
}
ENV_TEMPLATE = """# Dify の接続情報(このファイルは共有しないこと)
DIFY_BASE_URL=https://your-dify-host/v1
DIFY_API_KEY=app-xxxxxxxx
# 社内の証明書が必要な場合
# REQUESTS_CA_BUNDLE=C:\\path\\to\\corp-ca.pem
"""
NAME_MAP_HEADER = "product_type,past_name,code\n"


@dataclass
class ResolvedPaths:
    local_dir: Path | None
    codebook: Path
    columns: Path
    prompt: Path
    env_file: Path
    outputs_dir: Path
    name_map: Path | None


def _local(local_dir) -> Path | None:
    if local_dir:
        return Path(local_dir)
    v = os.environ.get(ENV_VAR)
    return Path(v) if v else None


def resolve_paths(local_dir=None, codebook=None, columns=None, prompt=None) -> ResolvedPaths:
    """設定ファイルを、明示指定 → ローカル作業フォルダ → リポジトリの初期値 の順で探す。"""
    local = _local(local_dir)

    def pick(explicit, rel):
        if explicit:
            return Path(explicit)
        if local is not None and (local / rel).exists():
            return local / rel
        return DEFAULTS[rel]

    name_map = local / "eval_name_map.csv" if local is not None else None
    return ResolvedPaths(
        local_dir=local,
        codebook=pick(codebook, "classification_codes.yaml"),
        columns=pick(columns, "input_columns.yaml"),
        prompt=pick(prompt, "prompts/system_prompt.md"),
        env_file=(local / ".env") if local is not None else REPO_ROOT / ".env",
        outputs_dir=(local / "outputs") if local is not None else REPO_ROOT / "outputs" / "v2",
        name_map=name_map if name_map is not None and name_map.exists() else None,
    )


def init_local(local_dir) -> list[Path]:
    """ローカル作業フォルダを作り、初期値をコピーする。既存のファイルは上書きしない。"""
    local = Path(local_dir)
    created: list[Path] = []
    for d in (local, local / "data", local / "outputs", local / "prompts"):
        if not d.exists():
            d.mkdir(parents=True)
            if d != local and d.name != "prompts":
                created.append(d)
    for rel, src in DEFAULTS.items():
        dst = local / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            created.append(dst)
    for rel, text in ((".env", ENV_TEMPLATE), ("eval_name_map.csv", NAME_MAP_HEADER)):
        dst = local / rel
        if not dst.exists():
            dst.write_text(text, encoding="utf-8-sig" if rel.endswith(".csv") else "utf-8")
            created.append(dst)
    return created
