import os
from typing import Optional

from pydantic import BaseModel

from logger import logger
from subtitle_types import CharacterInfo, Metadata, TermBank


class TermBankDTO(TermBank):
    @classmethod
    def from_term_bank(cls, term_bank: TermBank) -> "TermBankDTO":
        return cls(**term_bank.model_dump())

    def to_term_bank(self) -> TermBank:
        return TermBank(**self.model_dump())


class CharacterInfoDTO(CharacterInfo):
    @classmethod
    def from_character_info(cls, character_info: CharacterInfo) -> "CharacterInfoDTO":
        return cls(**character_info.model_dump())

    def to_character_info(self) -> CharacterInfo:
        return CharacterInfo(**self.model_dump())


class MetadataDTO(BaseModel):
    title: str
    title_alt: list[str] = []
    description: str = ""
    characters: list[CharacterInfoDTO] = []

    @classmethod
    def from_metadata(cls, metadata: Metadata) -> "MetadataDTO":
        return cls(
            **metadata.model_dump(
                exclude={"characters"},
            ),
            characters=[
                CharacterInfoDTO.from_character_info(c) for c in metadata.characters
            ],
        )

    def to_metadata(self) -> Metadata:
        return Metadata(
            **self.model_dump(
                exclude={"characters"},
            ),
            characters=[character.to_character_info() for character in self.characters],
        )


class Store(BaseModel):
    term_bank: Optional[TermBankDTO] = None
    metadata: Optional[MetadataDTO] = None

    @classmethod
    def load_from_file(cls, path: str) -> "Store":
        store_path = _find_pre_translate_store(path)
        stored = cls()

        try:
            with open(store_path, "r", encoding="utf-8") as file:
                stored = Store.model_validate_json(file.read())
        except Exception as e:
            logger.debug(f"Error loading pre-translate store: {e}")

        return stored

    def save_to_file(self, path: str) -> None:
        store_path = _find_pre_translate_store(path)
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        try:
            with open(store_path, "w", encoding="utf-8") as file:
                file.write(self.model_dump_json())
        except Exception as e:
            logger.error(f"Error saving pre-translate store: {e}")
            raise


def _find_pre_translate_store(path: str) -> str:
    return os.path.join(os.path.dirname(path), ".translate", "pre_translate_store.json")


def load_pre_translate_store(path: str) -> TermBank:
    """
    Loads the pre-translate store from a file.
    :param path: Path of the directory containing the pre-translate store.
    :return: List of dictionaries containing pre-translate context.
    """
    stored = Store.load_from_file(path)
    return stored.term_bank.to_term_bank() if stored.term_bank else TermBank(context={})


def save_pre_translate_store(path: str, pre_translate_context: TermBank) -> None:
    """
    Saves the pre-translate context to a file.
    :param path: Path of the directory containing the pre-translate store.
    :param pre_translate_context: List of dictionaries containing pre-translate context.
    """
    stored = Store.load_from_file(path)
    stored.term_bank = TermBankDTO.from_term_bank(pre_translate_context)
    stored.save_to_file(path)


def load_media_set_metadata(path: str) -> Optional[Metadata]:
    """
    Loads the media set metadata from a file.
    :param path: Path of the directory containing the media set metadata.
    :return: MediaSetMetadata object or None if not found.
    """
    stored = Store.load_from_file(path)
    return stored.metadata.to_metadata() if stored.metadata else None


def save_media_set_metadata(path: str, metadata: Metadata) -> None:
    """
    Saves the media set metadata to a file.
    :param path: Path of the directory containing the media set metadata.
    :param metadata: MediaSetMetadata object to save.
    """
    stored = Store.load_from_file(path)
    stored.metadata = MetadataDTO.from_metadata(metadata)
    stored.save_to_file(path)
