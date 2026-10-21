from pydantic import BaseModel
from backend.core.model.inject_session import inject_session


class first_conversation_data(BaseModel):
    limit_count: int
    position_id: str
    inject_session: inject_session