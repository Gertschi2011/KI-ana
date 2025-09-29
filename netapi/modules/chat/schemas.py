from pydantic import BaseModel
from typing import Optional
class ChatIn(BaseModel):
    message: str
    lang: Optional[str] = None
    persona: Optional[str] = None
