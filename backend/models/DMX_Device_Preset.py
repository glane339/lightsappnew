from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class DMX_Device_Preset(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    order: int
    channel_count: int
    channel_values: List[int]