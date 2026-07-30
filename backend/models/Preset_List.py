from pydantic import BaseModel
from typing import List, Optional
from models.Preset import Preset

class Preset_List(BaseModel):
    id: str
    Presets: List[Preset]