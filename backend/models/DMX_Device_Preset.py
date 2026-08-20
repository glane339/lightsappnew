from pydantic import BaseModel, Field, field_validator
from typing import List
from uuid import uuid4

from dmx_slots import require_dmx_slots

class DMX_Device_Preset(BaseModel):
    """
    One device's channel values inside a look.

    The channel count and start address come from the referenced DMX_Device, so a
    look never restates the patch. Each slot is a DMX512 value (0–255).
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    device_id: str
    channel_values: List[int] = []

    @field_validator("channel_values")
    @classmethod
    def _dmx_range(cls, values: List[int]) -> List[int]:
        return require_dmx_slots(values)
