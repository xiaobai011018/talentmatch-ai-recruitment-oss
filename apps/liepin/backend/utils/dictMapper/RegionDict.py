"""
----------------------------------------------------
 File Name:        RegionDict
 Author:           hoges
 Created Date:     2025/9/29
 Last Modified:    2025/9/29
 Python Version:   
----------------------------------------------------
"""
import json
from backend.config.mapperPathConfig import WANT_TO_REGION_MAPPER_PATH


class RegionDict:
    def __init__(self):
        with open(WANT_TO_REGION_MAPPER_PATH, "r", encoding="utf-8") as f:
            self.codeToName = json.load(f)
        self.nameToCode = {v: k for k, v in self.codeToName.items()}

    def get_name(self, code):
        return self.codeToName.get(code)

    def get_code(self, name):
        return self.nameToCode.get(name)