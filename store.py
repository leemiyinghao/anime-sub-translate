import json
import logging
import os
from typing import List, Optional

from pydantic import BaseModel

from subtitle_types import PreTranslatedContext

logger = logging.getLogger(__name__)


class PreTranslatedContextDTO(PreTranslatedContext):
    @classmethod
    def from_context(cls, context: PreTranslatedContext) -> "PreTranslatedContextDTO":
        return cls(**context.model_dump())

    def to_context(self) -> PreTranslatedContext:
        return PreTranslatedContext(**self.model_dump())


class Store(BaseModel):
    context: Optional[List[PreTranslatedContextDTO]] = None

    @classmethod
    def load_from_file(cls, path: str) -> "Store":
        store_path = _find_pre_translate_store(path)
        stored = cls()

        try:
            with open(store_path, "r", encoding="utf-8") as file:
                stored = Store.model_validate_json(file.read())
        except Exception as e:
            logger.warning(f"Error loading pre-translate store: {e}")

        return stored

    def save_to_file(self, path: str) -> None:
        store_path = _find_pre_translate_store(path)
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        try:
            with open(store_path, "w", encoding="utf-8") as file:
                file.write(self.model_dump_json())
        except Exception as e:
            logger.warning(f"Error saving pre-translate store: {e}")


def _find_pre_translate_store(path: str) -> str:
    return os.path.join(os.path.dirname(path), ".translate", "pre_translate_store.json")


def load_pre_translate_store(path: str) -> List[PreTranslatedContext]:
    """
    Loads the pre-translate store from a file.
    :param path: Path of the directory containing the pre-translate store.
    :return: List of dictionaries containing pre-translate context.
    """
    stored = Store.load_from_file(path)
    return (
        [context.to_context() for context in stored.context] if stored.context else []
    )


def save_pre_translate_store(
    path: str,
    pre_translate_context: List[PreTranslatedContext],
) -> None:
    """
    Saves the pre-translate context to a file.
    :param path: Path of the directory containing the pre-translate store.
    :param pre_translate_context: List of dictionaries containing pre-translate context.
    """
    stored = Store.load_from_file(path)
    stored.context = [
        PreTranslatedContextDTO.from_context(context)
        for context in pre_translate_context
    ]
    stored.save_to_file(path)
