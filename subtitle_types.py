# type hint for subtitle format
from typing import Optional

from pydantic import BaseModel
from typing_extensions import deprecated


class Dialogue(BaseModel):
    id: str
    content: str
    actor: Optional[str] = None
    style: Optional[str] = None


@deprecated("Use TermBank instead")
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


class Metadata(BaseModel):
    """
    Metadata for the media set.
    """

    title: str
    title_alt: list[str] = []
    description: str = ""
    characters: list[CharacterInfo] = []


class TermBankItem(BaseModel):
    """
    Term bank item for the subtitle.
    """

    translated: str
    description: Optional[str] = None


class TermBank(BaseModel):
    """
    Term bank for the subtitle.
    """

    context: dict[str, TermBankItem]

    def update(self, term_bank: "TermBank") -> "TermBank":
        """
        Update the term bank with a new term.
        """
        self.context.update(term_bank.context)
        return self

    def __bool__(self) -> bool:
        """
        Check if the term bank is empty.
        """
        return bool(self.context)

    def __eq__(self, other: object) -> bool:
        """
        Check if the term bank is equal to another term bank.
        """
        if other is None and not self.context:
            return True
        if not isinstance(other, TermBank):
            return False
        return self.context == other.context
