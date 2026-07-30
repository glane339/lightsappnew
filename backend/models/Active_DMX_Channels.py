from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

UNIVERSE_SIZE = 512

class Active_DMX_Channels(BaseModel):
    """The one channel map the DMX sender reads. Rebuilt in place, never persisted."""
    channels: List[int] = Field(default_factory=lambda: [0] * UNIVERSE_SIZE)
