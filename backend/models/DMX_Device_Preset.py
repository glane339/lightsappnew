from pydantic import BaseModel
from typing import List, Optional

class DMX_Device_Preset(BaseModel):
    id: str
    order: int
    channel_count: int
    channel_values: List[int]