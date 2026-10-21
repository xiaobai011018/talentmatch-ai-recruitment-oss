# -*- coding: utf-8 -*-
"""校验 smart_keywords 括号归一化逻辑。"""
from backend.core.entity.candidate import Candidate


def main() -> None:
    collapse = Candidate._collapse_spaces

    assert collapse('光点（上海）国际贸易有限公司') == collapse('光点(上海)国际贸易有限公司')
    assert collapse('光点【上海】国际贸易有限公司') == collapse('光点(上海)国际贸易有限公司')
    assert collapse('某某( 北京 )科技') == collapse('某某(北京)科技')
    assert collapse('某某\u3000(北京)\u3000科技') == collapse('某某(北京)科技')

    kw_a = Candidate._build_smart_keywords(
        '张三', '光点【上海】国际贸易有限公司', '工程师', '北大', '计算机'
    )
    kw_b = Candidate._build_smart_keywords(
        '张三', '光点(上海)国际贸易有限公司', '工程师', '北大', '计算机'
    )
    assert kw_a == kw_b

    # 研发前缀变体逻辑不应被括号归一化破坏
    cands = Candidate._build_smart_keyword_candidates(
        '张三', '某某科技', '研发(后端)工程师', '北大', '计算机'
    )
    assert len(cands) == 4  # 2 分隔符 × 2 职位变体
    assert any('(后端)工程师' in c for c in cands)
    assert any('后端)工程师' in c for c in cands)

    print('smart_keywords bracket assertions passed')


if __name__ == '__main__':
    main()
