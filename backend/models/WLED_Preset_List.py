from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class WLED_Preset_List(BaseModel):
    """
    An ordered cue list of LEDfx scenes, plus how long each one holds.

    ``beats`` applies to every entry, matching ``DMX_Preset_List``. A value below 1 is
    rejected: zero would mean either "advance infinitely fast" or "never advance",
    and neither is a thing an operator can have meant.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    wled_preset_ids: List[str] = []
    beats: int = Field(default=1, ge=1)
