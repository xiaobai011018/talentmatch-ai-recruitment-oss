from typing import List

from pydantic import BaseModel


class reply_model(BaseModel):
    position_id: str
    cookies_file_name_list: List[str]
    reply_mode: str
    hunter_mode:bool