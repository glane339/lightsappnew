from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

class Scene(BaseModel):
    """
    The top-level, manually selected unit of a show.

    ``ilda_frame_list_id`` is optional: laser support is parked, so a scene is
    complete without one. Making it required again is all it takes to bring the ILDA
    path back into the graph.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    preset_id: str
    ilda_frame_list_id: Optional[str] = None
