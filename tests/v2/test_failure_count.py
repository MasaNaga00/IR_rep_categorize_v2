"""R-27, R-28: 故障数(丸数字の最大値)。"""
from __future__ import annotations

import pytest

from repclass.failure_count import count_failures


@pytest.mark.parametrize("text, count, present, missing", [
    ("電源が入らない", 1, set(), []),
    ("", 1, set(), []),                                   # R-28 空欄
    ("①AFが合わない ②液晶にスジ", 2, {1, 2}, []),
    ("①電源が落ちる ②止まる ③②の後に熱くなる", 3, {1, 2, 3}, []),  # 引用があっても最大値
    ("①シャッター ③背面ボタン", 3, {1, 3}, [2]),          # 番号飛び
    ("【修理上限金額：100000円】背面のダイヤル", 1, set(), []),
    ("⑪から⑳まで: ⑳", 20, {11, 20}, list(range(1, 11)) + list(range(12, 20))),
    ("メンテナンスで入庫しましたが、修理に移行しました。①A ②B", 2, {1, 2}, []),
])
def test_r27_count_failures(text, count, present, missing):
    r = count_failures(text)
    assert r.failure_count == count
    assert set(r.present_numbers) == present
    assert list(r.missing_numbers) == missing


def test_r27_none_is_treated_as_empty():
    assert count_failures(None).failure_count == 1
