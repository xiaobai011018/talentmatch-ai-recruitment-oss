from typing import List,Optional

from pydantic import BaseModel


class save_resume_data(BaseModel):
    reply_mode:str
    start_time:str
    end_time:str
    position_id: str
    hunter_mode:bool
    cookies_file_name_list: List[str]
    son_position_id_list: Optional[List[str]] = None
    fs_cookies_file_name: Optional[str] = None
    fs_position_name: Optional[str] = None
