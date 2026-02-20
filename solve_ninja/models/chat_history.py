from typing import Optional
from pydantic import BaseModel
from typing import Dict, Any

class ChatHistory(BaseModel):
    user_message: str
    role: str
    response_type: str
    use_case: str
    session_id: Optional[str] = None
    event_id: Optional[str] = None
    user: Optional[str] = None
    done_signal_count: Optional[int] = 0
    name: Optional[str] = None
    sequence_number: Optional[int] = 0