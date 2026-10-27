from pydantic import BaseModel
from typing import Optional

class CaptureAgent(BaseModel):
    name: str
    display: str
    state: str
    # Timestamps — may be None if never set
    time_since_last_update: Optional[int] = None
    last_updated: Optional[str] = None
