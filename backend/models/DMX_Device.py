from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

from models.Active_DMX_Channels import UNIVERSE_SIZE

class DMX_Device(BaseModel):
    """
    One physical fixture in the rig, and where it is patched.

    ``model`` names the channel table in docs/fixtures/; the per-channel meaning is
    documented there rather than stored, so the library only has to know how many
    channels the device occupies and where they start.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    model: Optional[str] = None
    mode: Optional[str] = None
    universe: int = Field(default=1, ge=1)
    start_address: int = Field(ge=1, le=UNIVERSE_SIZE)
    channel_count: int = Field(ge=1, le=UNIVERSE_SIZE)

    @property
    def end_address(self) -> int:
        """Last channel this device occupies, inclusive."""
        return self.start_address + self.channel_count - 1
