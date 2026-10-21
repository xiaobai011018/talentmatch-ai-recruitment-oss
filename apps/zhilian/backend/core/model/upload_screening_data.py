"""
----------------------------------------------------
 File Name:        injectRespone
 Author:           hoges
 Created Date:     2025/10/17
 Last Modified:    2025/10/17
 Python Version:   
----------------------------------------------------
"""
from pydantic import BaseModel
from backend.core.model.inject_session import inject_session

class upload_screening_data(BaseModel):
    hunterId: str
    position_id : str
    positionName : str
    inject_session: inject_session
