"""共通の定数。"""
from __future__ import annotations

NO_CLAIM = "NO_CLAIM"            # 番号飛びの行のユーザ視点コード(R-42)
NO_CLAIM_NAME = "申告なし"

BASIS_VALUES = ("direct", "same_cause", "none")
SOURCE_VALUES = ("user", "repair", "both")
RESPONSIBILITY_VALUES = ("manufacturer", "user_or_unknown")
RECORD_TYPES = ("failure", "service", "unknown")
REQUIRED_ROLES = ("connected_device", "other", "unknown")
SPECIAL_ENV_KEYS = ("none", "unknown")  # LLM 出力では使わない(R-18)

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"

SEP = ";"                         # 最終出力で複数の値を連結する区切り
