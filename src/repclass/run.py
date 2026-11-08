"""python -m repclass.run(R-49)。結果の要約は短く表示する(R-57)。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .codebook import CodebookError, load_codebook
from .comment_preprocess import PreprocessConfigError, load_preprocess_rules
from .input_loader import load_column_config
from .local_config import resolve_paths
from .pipeline import run_pipeline


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="修理データ分類パイプライン v2")
    ap.add_argument("--input", required=True, help="入力 CSV")
    ap.add_argument("--local-dir", help="ローカル作業フォルダ(環境変数 REPCLASS_LOCAL_DIR でも可)")
    ap.add_argument("--codebook")
    ap.add_argument("--columns")
    ap.add_argument("--prompt", help="実行メタ情報に記録するプロンプトファイル")
    ap.add_argument("--preprocess", help="注記の除去の設定ファイル(既定: ローカル作業フォルダの comment_preprocess.yaml)")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--output-dir")
    ap.add_argument("--resume", help="再実行する前回の timestamp(または実行フォルダのパス)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-internal", action="store_true", help="内部コメントも LLM に渡す(既定: 渡さない)")
    ap.add_argument("--verbose", action="store_true")
    return ap


def main(argv=None, client=None) -> int:
    a = _parser().parse_args(argv)
    paths = resolve_paths(local_dir=a.local_dir, codebook=a.codebook, columns=a.columns, prompt=a.prompt,
                          preprocess=a.preprocess)
    try:
        codebook = load_codebook(paths.codebook)
    except CodebookError as e:
        print(f"NG: コード体系にエラーがあります({len(e.errors)} 件)。python -m repclass.check_codebook で確認してください。")
        return 2
    try:
        preprocess = load_preprocess_rules(paths.preprocess)
    except (PreprocessConfigError, OSError, ValueError) as e:
        print(f"NG: 注記の除去の設定(comment_preprocess.yaml)にエラーがあります: {e}")
        return 2
    output_dir = Path(a.output_dir) if a.output_dir else paths.outputs_dir
    resume = None
    if a.resume:
        resume = Path(a.resume) if Path(a.resume).exists() else output_dir / a.resume
        if not resume.exists():
            print(f"NG: 再実行元が見つかりません: {a.resume}")
            return 2
    if client is None and not a.dry_run:
        from .dify_client import DifyClient
        client = DifyClient.from_env(env_file=paths.env_file)
    res = run_pipeline(a.input, codebook=codebook, client=client, output_dir=output_dir,
                       batch_size=a.batch_size, columns=load_column_config(paths.columns),
                       include_internal=a.include_internal, resume_from=resume, dry_run=a.dry_run,
                       prompt_path=paths.prompt, preprocess=preprocess)
    m = res.meta
    print(f"実行フォルダ: {res.run_dir}")
    c = m["counts"]

    def excluded_summary():
        if not c["excluded"]:
            return
        reasons = " / ".join(f"{k} {v}" for k, v in m["excluded_reasons"].items())
        print(f"除外の内訳: {reasons}(一覧: excluded_rows.csv)")
        unk = m.get("unknown_product_values") or {}
        if unk:
            items = list(unk.items())
            print("YAML にない製品種別: " + ", ".join(f"{v!r}({n})" for v, n in items[:5])
                  + (f" ...ほか {len(items) - 5} 種類" if len(items) > 5 else "")
                  + f"  / YAML の製品ID: {', '.join(codebook.product_ids())}")
    def notes_summary():
        pp = m.get("preprocess")
        if not pp:
            return
        marks = ", ".join(pp["markers"]) or "なし"
        print(f"注記を取り除いた修理: {pp['repairs_with_notes']} 件(マーク: {marks})(一覧: removed_notes.csv)")
        if pp["markers"] and pp["repairs_with_notes"] == 0:
            print(f"  注意: 1件も取り除かれませんでした。マークの文字が実データと合っていない可能性があります: {paths.preprocess}")
    if a.dry_run:
        print(f"dry-run: 入力 {c['input']} / 除外 {c['excluded']} / 送信予定 {c['to_run']} / バッチ {m['batches']}")
        excluded_summary()
        notes_summary()
        return 0
    print(f"入力 {c['input']} / 除外 {c['excluded']} / ok {c['ok']} / warning {c['warning']} / error {c['error']}")
    excluded_summary()
    notes_summary()
    print(f"メーカー責任修理 YES: {m['manufacturer_repair_yes']} / バッチ {m['batches']} / 再試行 {m['retries']} / 所要 {m['elapsed_seconds']} 秒")
    errors = [r for r in res.final_rows if r["status"] == "error"]
    if errors:
        print(f"エラーの修理(先頭5件): " + ", ".join(f"{r['repair_id']}({r['error_reason']})" for r in errors[:5]))
        print(f"再実行: python repclass_cli.py run --input {a.input} --resume {res.run_dir.name}" + (f" --local-dir {a.local_dir}" if a.local_dir else ""))
    if a.verbose:
        for r in errors:
            print(f"  {r['repair_id']}: {r['error_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
