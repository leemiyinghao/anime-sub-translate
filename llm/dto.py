import json
import re
from abc import ABC, abstractmethod
from typing import Annotated, Dict, Iterable, List, Type, TypeVar

from pydantic import BaseModel, BeforeValidator
from subtitle_types import PreTranslatedContext, SubtitleDialogue

__all__ = [
    "dump_json",
    "parse_json",
    "SubtitleDialogueRequestDTO",
    "SubtitleDialogueResponseDTO",
    "DialogueSetRequestDTO",
    "DialogueSetResponseDTO",
    "PreTranslatedContextDTO",
    "PreTranslatedContextSetDTO",
]

T = TypeVar("T", bound=BaseModel)


def obj_or_json(model: Type[T], obj: T | str) -> T:
    """
    Converts a string to a JSON object or returns the object as is.
    Aiming to solve double-serialization issue experienced with Gemini 2.0 Flash.
    """
    if isinstance(obj, str):
        return model.model_validate_json(obj)
    return obj


def dump_json(obj: object | BaseModel) -> str:
    """
    Dumps a Python object to a JSON string.
    :param obj: The object to dump.
    :return: The JSON string.
    """
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    return json.dumps(obj, ensure_ascii=False)


def parse_json(model: Type[T], json_str: str) -> T:
    """
    Parses a JSON string to a Python object.
    :param model: The model to parse the JSON string into.
    :param json_str: The JSON string to parse.
    :return: The parsed object.
    """
    # remove code block wrapper
    if json_str.startswith("```json") and json_str.endswith("```"):
        json_str = json_str[7:-3].strip()
    return model.model_validate_json(json_str)


class PromptedDTO(ABC):
    @classmethod
    @abstractmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        pass


class SubtitleDialogueRequestDTO(SubtitleDialogue):
    """
    Request DTO for subtitle dialogue.
    """

    @classmethod
    def from_subtitle(cls, subtitle: SubtitleDialogue) -> "SubtitleDialogueRequestDTO":
        """
        Converts a SubtitleDialogue to a SubtitleDialogueRequestDTO.
        """
        return cls(**subtitle.model_dump())


class SubtitleDialogueResponseDTO(BaseModel):
    """
    Response DTO for subtitle dialogue.
    """

    id: str
    content: str

    def to_subtitle(self) -> SubtitleDialogue:
        """
        Converts a SubtitleDialogueResponseDTO to a SubtitleDialogue.
        """
        # LLMs have a tendency to over-escape backslashes.
        transformed_content = re.sub(r"\\+", "\\\\", self.content)
        transformed_content = re.sub(r"\\n", "\n", transformed_content)
        return SubtitleDialogue(
            **self.model_dump(exclude={"content"}), content=transformed_content
        )


class DialogueSetRequestDTO(BaseModel):
    """
    Request DTO for dialogues translation.
    """

    subtitles: List[SubtitleDialogueRequestDTO]

    @classmethod
    def from_subtitle(
        cls, subtitles: Iterable[SubtitleDialogue]
    ) -> "DialogueSetRequestDTO":
        """
        Converts a list of SubtitleDialogue to a DialogueSetRequestDTO.
        """
        return cls(
            subtitles=[SubtitleDialogueRequestDTO.from_subtitle(i) for i in subtitles]
        )


class DialogueSetResponseDTO(BaseModel, PromptedDTO):
    """
    Response DTO for dialogues translation.
    """

    translated: Dict[str, str]

    def to_subtitles(self) -> list[SubtitleDialogue]:
        """
        Converts a DialogueSetResponseDTO to a list of SubtitleDialogue.
        """
        return [SubtitleDialogue(id=i, content=j) for i, j in self.translated.items()]

    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """Provide translated result in a dictionary contain sets of subtitles with their IDs as keys and translated content as values.\nExample: `{"translated":{"1": "Hello", "2.0": "World"}}`."""


class PreTranslatedContextDTO(PreTranslatedContext):
    """
    DTO for pre-translated context.
    """

    @classmethod
    def from_context(cls, context: PreTranslatedContext) -> "PreTranslatedContextDTO":
        """
        Converts a PreTranslatedContext to a PreTranslatedContextDTO.
        """
        return cls(**context.model_dump())

    def to_context(self) -> PreTranslatedContext:
        """
        Converts a PreTranslatedContextDTO to a PreTranslatedContext.
        """
        return PreTranslatedContext(**self.model_dump())


class PreTranslatedContextSetDTO(BaseModel):
    """
    DTO for context set.
    """

    context: Annotated[
        List[PreTranslatedContextDTO],
        BeforeValidator(lambda v: [obj_or_json(PreTranslatedContextDTO, i) for i in v]),
    ]

    @classmethod
    def from_contexts(
        cls, context: Iterable[PreTranslatedContext]
    ) -> "PreTranslatedContextSetDTO":
        """
        Converts a list of PreTranslatedContext to a PreTranslatedContextSetDTO.
        """
        return cls(context=[PreTranslatedContextDTO.from_context(i) for i in context])

    def to_contexts(self) -> List[PreTranslatedContext]:
        """
        Converts a PreTranslatedContextSetDTO to a list of PreTranslatedContext.
        """
        return [i.to_context() for i in self.context]


class PreTranslatedContextSetResponseDTO(PreTranslatedContextSetDTO, PromptedDTO):
    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """Provide translation context note as the follow example: `{"context":[{"original":"Hello","translated":"你好"},{"original":"Sekai","translated":"世界","description":"The same as world."}]}`, `original` is term in source language, `translated` is term in target language, description is optional."""
