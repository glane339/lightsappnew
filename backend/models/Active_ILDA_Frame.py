from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class Active_ILDA_Frame(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    frame_id: str
