# type hint for subtitle format
from typing import Optional
from typing_extensions import TypedDict


class SubtitleDialogue(TypedDict):
    id: int
    content: str


class RichSubtitleDialogue(SubtitleDialogue):
    id: int
    content: str
    actor: Optional[str]
    style: Optional[str]


class PreTranslatedContext(TypedDict):
    original: str
    translated: str
    description: Optional[str]
