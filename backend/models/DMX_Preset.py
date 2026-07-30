from pydantic import BaseModel
from typing import List, Optional
from models.DMX_Device_Preset import DMX_Device_Preset

class DMX_Preset(BaseModel):
    id: str
    DMX_Device_Presets: List[DMX_Device_Preset]
