from pydantic import BaseModel
from typing import List


class first_conversation_with_excel_data(BaseModel):
    limit_count: int
    excel_name:str
    cookies_file_name_list: List[str]
