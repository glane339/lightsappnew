from pydantic import BaseModel
from typing import List, Optional

class WLED_Preset(BaseModel):
    id: str