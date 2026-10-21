# -*- coding: utf-8 -*-
"""本地校验 upload_resume 金币规则（不调用外部 API）。"""
from backend.core.entity.candidate import compute_upload_resume_coins_cost as f


def main() -> None:
    cases = [
        ("不匹配", "a候选人b", "1", 30),
        ("不匹配", "no reply", "1", 20),
        ("不确定", "候选人", "强意向", 30),
        ("不确定", "", "0", 20),
        ("匹配", "", "0", 40),
        ("非常匹配", "", "0", 40),
        ("匹配", "候选人", "0", 50),
        ("匹配", "候选人", "256", 80),
        ("非常匹配", "候选人", "256", 80),
        ("非常匹配", "候选人", "109", 60),
        ("非常匹配", "候选人", "110", 60),
        ("非常匹配", "候选人", "104", 80),
        ("非常匹配", "候选人", "105", 80),
        ("非常匹配", "候选人", "107", 80),
        ("非常匹配", "候选人", "200", 60),
        ("非常匹配", "候选人", "50", 80),
        ("匹配", "候选人", "强意向标签", 80),
        ("非常匹配", "候选人", "强意向", 80),
    ]
    for label, ch, st, exp in cases:
        got = f(label, ch, st)
        assert got == exp, (label, ch, st, got, exp)
    assert f("非常匹配", "候选人", "not-a-number") == 60
    print("compute_upload_resume_coins_cost: all assertions passed")


if __name__ == "__main__":
    main()
