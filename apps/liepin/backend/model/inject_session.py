from typing import Optional, Dict, Any, List

from pydantic import BaseModel


class inject_session(BaseModel):
    cookies_file_name_list: List[str]
    strategyMode: str
    strategy_name_list: Optional[List[str]] = None
    strategy_list : Optional[List[Dict[str,Any]]] = None