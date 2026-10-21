from typing import List, Optional

from pydantic import BaseModel

from backend.model.inject_session import inject_session


class all_auto_data(BaseModel):
    reply_mode: str
    hunter_id: str
    position_id: str
    position_name: str
    fs_position_name: Optional[str] = None
    fs_cookies_file_name: Optional[str] = None
    limit_count: int
    start_time: str
    end_time: str
    save_resume_time: str
    conversation_mode: str
    hunter_mode:bool = False
    excel_file_name_list: Optional[List[str]] = None
    son_position_id_list: Optional[List[str]] = None
    selected_process: List[str]
    inject_session: inject_session
