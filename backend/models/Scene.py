from pydantic import BaseModel
from typing import List, Optional
from models.Preset_List import Preset_List
from models.ILDA_Frame_List import ILDA_Frame_List

class Scene(BaseModel):
    id: str
    Preset_List: Preset_List
    ILDA_Frame_List: ILDA_Frame_List
    Sensitivity: float
