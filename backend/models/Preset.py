from pydantic import BaseModel
from typing import List, Optional
from models.DMX_Preset import DMX_Preset
from models.WLED_Preset import WLED_Preset

class Preset(BaseModel):
    id: str
    DMX_Preset: DMX_Preset
    WLED_Preset: WLED_Preset
