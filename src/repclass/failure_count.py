"""R-27, R-28: 故障数(ユーザコメント中の丸数字の最大値)。"""
from __future__ import annotations

from dataclasses import dataclass, field

# ①(U+2460)〜⑳(U+2473)
CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)}


@dataclass(frozen=True)
class FailureCountResult:
    failure_count: int
    present_numbers: frozenset[int] = field(default_factory=frozenset)
    missing_numbers: tuple[int, ...] = ()


def count_failures(user_comment: str | None) -> FailureCountResult:
    text = user_comment or ""
    present = frozenset(CIRCLED[ch] for ch in text if ch in CIRCLED)
    if not present:
        return FailureCountResult(1, frozenset(), ())
    n = max(present)
    missing = tuple(i for i in range(1, n + 1) if i not in present)
    return FailureCountResult(n, present, missing)
