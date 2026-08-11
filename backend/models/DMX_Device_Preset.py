from pydantic import BaseModel, Field
from typing import List
from uuid import uuid4

class DMX_Device_Preset(BaseModel):
    """
    One device's channel values inside a look.

    The channel count and start address come from the referenced DMX_Device, so a
    look never restates the patch.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    device_id: str
    channel_values: List[int] = []
