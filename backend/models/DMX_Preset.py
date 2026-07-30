from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class DMX_Preset(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    dmx_device_preset_ids: List[str] = []
