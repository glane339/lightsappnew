from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class WLED_Preset(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)