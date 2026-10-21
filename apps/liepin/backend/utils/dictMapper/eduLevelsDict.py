"""
----------------------------------------------------
 File Name:        eduLevelsDict
 Author:           hoges
 Created Date:     2025/9/29
 Last Modified:    2025/9/29
 Python Version:   3.11
----------------------------------------------------
"""
import json
from pathlib import Path
from backend.config.mapperPathConfig import EDU_LEVEL_MAPPER_PATH
from collections import defaultdict
from typing import List, Optional


class EduLevelDict:
    def __init__(self):
        # 自动处理文件路径
        path = Path(EDU_LEVEL_MAPPER_PATH)
        if not path.exists():
            raise FileNotFoundError(f"字典文件不存在: {EDU_LEVEL_MAPPER_PATH}")

        # 加载学历字典（code -> name list）
        with path.open("r", encoding="utf-8") as f:
            self.nameToCodes: dict[str, List[str]] = json.load(f)

        # 构造 code -> name 映射（一个 code 对应多个学历时取最近匹配的最高学历）
        self.codeToNames: dict[str, List[str]] = defaultdict(list)
        for name, codes in self.nameToCodes.items():
            for code in codes:
                self.codeToNames[code].append(name)

    def code_to_name(self, code: str) -> Optional[List[str]]:
        """
        根据 code 获取学历列表（可能有多个学历对应同一个 code）
        """
        return self.codeToNames.get(code)

    def name_to_code(self, name: str) -> Optional[List[str]]:
        """
        根据学历名称获取对应的 code 列表
        """
        return self.nameToCodes.get(name)
