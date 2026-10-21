from typing import List, Optional

from pydantic import BaseModel

from backend.core.model.inject_session import inject_session


class all_auto_data(BaseModel):
    reply_mode:str
    hunter_id:str
    position_id:str
    position_name:str
    limit_count:int
    start_time:str
    end_time:str
    save_resume_time:str
    selected_process: List[str]
    inject_session:inject_session
    excel_name : Optional[str] = None
    cookies_file_name_list : Optional[List[str]] = None