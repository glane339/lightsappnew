from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class Active_DMX_Channels(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    channels: List[int]
