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


class CharacterInfo(BaseModel):
    """
    Character information for the subtitle.
    """

    name: str
    name_alt: list[str] = []
    gender: str


class MediaSetMetadata(BaseModel):
    """
    Metadata for the media set.
    """

    title: str
    title_alt: list[str] = []
    description: str = ""
    characters: list[CharacterInfo] = []
