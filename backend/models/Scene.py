from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class Scene(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    preset_list_id: str
    ilda_frame_list_id: str
    Sensitivity: float
