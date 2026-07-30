from pydantic import BaseModel
from typing import List, Optional

class Active_DMX_Channels(BaseModel):
    id: str
    channels: List[int]
