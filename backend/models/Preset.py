from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class Preset(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    dmx_preset_list_id: str
    wled_preset_id: str
