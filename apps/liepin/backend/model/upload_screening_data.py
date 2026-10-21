"""
----------------------------------------------------
 File Name:        injectRespone
 Author:           hoges
 Created Date:     2025/10/17
 Last Modified:    2025/10/17
 Python Version:   
----------------------------------------------------
"""
from typing import Optional
from pydantic import BaseModel

class upload_screening_data(BaseModel):
    hid: int
    pid : int
    cookies_file_names:list[str]
    strategy_names:Optional[list[str]]
    sids:Optional[list[int]]
