"""
----------------------------------------------------
 File Name:        industyDict
 Author:           hoges
 Created Date:     2025/9/30
 Last Modified:    2025/9/30
 Python Version:   
----------------------------------------------------
"""
import json
from typing import Dict, Optional

class IndustryDict:
    def __init__(self, json_path: str = "industries.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.code_to_name: Dict[str, str] = {}
        self.name_to_code: Dict[str, str] = {}

        for item in data:
            name = item.get("name")
            code = item.get("code")
            if name and code:
                self.code_to_name[code] = name
                self.name_to_code[name] = code

    def code_to_chName(self, code: str) -> Optional[str]:
        """根据 code 获取中文名"""
        return self.code_to_name.get(code)

    def chName_to_code(self, name: str) -> Optional[str]:
        """根据中文名获取 code"""
        return self.name_to_code.get(name)

