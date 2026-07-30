from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4

class Active_ILDA_Frame(BaseModel):
    """The one frame the ILDA sender reads. Empty until a scene is applied."""
    frame_id: Optional[str] = None
