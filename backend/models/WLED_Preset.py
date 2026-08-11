from pydantic import BaseModel


class WLED_Preset(BaseModel):
    """A LedFx scene mirrored into the library. ``id`` is the LedFx scene name."""

    id: str
