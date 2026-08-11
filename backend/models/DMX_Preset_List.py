from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class DMX_Preset_List(BaseModel):
    """
    An ordered cue list of looks, plus how long each one holds.

    ``beats`` applies to every entry in the list: the sequencer moves to the next look
    once that many beats have arrived. It is a property of the list rather than of a
    look, so the same look can hold for different lengths in different lists.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    dmx_preset_ids: List[str] = []
    beats: int = Field(default=1, ge=1)
