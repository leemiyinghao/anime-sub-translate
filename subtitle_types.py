# type hint for subtitle format
from typing import Optional

from pydantic import BaseModel


class SubtitleDialogue(BaseModel):
    id: str
    content: str
    actor: Optional[str] = None
    style: Optional[str] = None


class PreTranslatedContext(BaseModel):
    original: str
    translated: str
    description: Optional[str] = None
