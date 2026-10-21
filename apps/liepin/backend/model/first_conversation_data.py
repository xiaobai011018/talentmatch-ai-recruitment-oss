from typing import List, Optional

from pydantic import BaseModel
from backend.model.inject_session import inject_session


class first_conversation_data(BaseModel):
    limit_count: int
    position_id: str
    conversation_mode : str
    excel_file_name_list: Optional[List[str]] = None
    inject_session: inject_session