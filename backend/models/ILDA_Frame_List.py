from pydantic import BaseModel
from typing import List, Optional
from models.ILDA_Frame import ILDA_Frame

class ILDA_List(BaseModel):
    id: str
    ILDA_Frames: List[ILDA_Frame]
