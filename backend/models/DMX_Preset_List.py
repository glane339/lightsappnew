from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class DMX_Preset_List(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    dmx_preset_ids: List[str] = []
