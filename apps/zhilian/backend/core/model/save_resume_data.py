from typing import List

from pydantic import BaseModel


class save_resume_data(BaseModel):
    reply_mode:str
    start_time:str
    end_time:str
    position_id: str
    cookies_file_name_list: List[str]
