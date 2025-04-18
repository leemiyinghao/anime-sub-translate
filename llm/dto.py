import json
import re
from abc import ABC, abstractmethod
from typing import Annotated, Dict, Iterable, List, Type, TypeVar

from pydantic import AfterValidator, BaseModel, BeforeValidator
from subtitle_types import (
    CharacterInfo,
    Dialogue,
    Metadata,
    PreTranslatedContext,
    TermBank,
    TermBankItem,
)
from typing_extensions import deprecated

from .utils import clear_indentation

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
        result = ""
        if isinstance(obj, PromptedDTO):
            result += f"For the following JSON object, {obj.prompt()}\n"
        result += f"`{obj.model_dump_json(exclude_none=True)}`"
        return result

    return json.dumps(obj, ensure_ascii=False)


def parse_json(model: Type[T], json_str: str) -> T:
    """
    Parses a JSON string to a Python object.
    :param model: The model to parse the JSON string into.
    :param json_str: The JSON string to parse.
    :return: The parsed object.
    """
    # remove code block wrapper or other useless prefix/suffix
    # find first `{`
    start = json_str.find("{")
    # find last `}`
    end = json_str.rfind("}")
    if start != -1 and end != -1 and start < end:
        json_str = json_str[start : end + 1]
    else:
        raise ValueError("Invalid JSON string")
    return model.model_validate_json(json_str)


@deprecated("PromptedDTO is deprecated, don't use it.")
class PromptedDTO(ABC):
    @classmethod
    @abstractmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        pass


@deprecated("SubtitleDialogueRequestDTO is deprecated, use SubtitleDTO instead.")
class SubtitleDialogueRequestDTO(Dialogue):
    """
    Request DTO for subtitle dialogue.
    """

    @classmethod
    def from_subtitle(cls, subtitle: Dialogue) -> "SubtitleDialogueRequestDTO":
        """
        Converts a SubtitleDialogue to a SubtitleDialogueRequestDTO.
        """
        return cls(**subtitle.model_dump())


@deprecated("SubtitleDialogueResponseDTO is deprecated, use SubtitleDeltaDTO instead.")
class SubtitleDialogueResponseDTO(BaseModel):
    """
    Response DTO for subtitle dialogue.
    """

    id: str
    content: str

    def to_subtitle(self) -> Dialogue:
        """
        Converts a SubtitleDialogueResponseDTO to a SubtitleDialogue.
        """
        # LLMs have a tendency to over-escape backslashes.
        transformed_content = re.sub(r"\\+", "\\\\", self.content)
        transformed_content = re.sub(r"\\n", "\n", transformed_content)
        return Dialogue(
            **self.model_dump(exclude={"content"}), content=transformed_content
        )


@deprecated("DialogueSetRequestDTO is deprecated, use SubtitleDTO instead.")
class DialogueSetRequestDTO(BaseModel, PromptedDTO):
    """
    Request DTO for dialogues translation.
    """

    subtitles: List[SubtitleDialogueRequestDTO]

    @classmethod
    def from_subtitle(cls, subtitles: Iterable[Dialogue]) -> "DialogueSetRequestDTO":
        """
        Converts a list of SubtitleDialogue to a DialogueSetRequestDTO.
        """
        return cls(
            subtitles=[SubtitleDialogueRequestDTO.from_subtitle(i) for i in subtitles]
        )

    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """each item in `subtitles` is a subtitle dialogue in format of `{"id": "{id, return it directly}", "content": "{untranslated source content}","actor":"{character name about dialogue, optional, do not return},"style":"{visual style name of dialogue in subtitle, optional, do not return}"}`, order by the time of subtitle."""


@deprecated("DialogueSetResponseDTO is deprecated, use SubtitleDeltaDTO instead.")
class DialogueSetResponseDTO(BaseModel, PromptedDTO):
    """
    Response DTO for dialogues translation.
    """

    translated: Dict[str, str]

    def to_subtitles(self) -> list[Dialogue]:
        """
        Converts a DialogueSetResponseDTO to a list of SubtitleDialogue.
        """
        return [Dialogue(id=i, content=j) for i, j in self.translated.items()]

    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """Provide translated result in format of `{"translated":{"{id}":"{translated_content}"}}`. All ids from source must included. Only existed ids from source are allowed."""


@deprecated("PreTranslatedContextDTO is deprecated, use TermBankDTO instead.")
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


@deprecated("PreTranslatedContextSetDTO is deprecated, use TermBankDTO instead.")
class PreTranslatedContextSetDTO(BaseModel, PromptedDTO):
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

    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """each item in `context` is a context note in format of `{"original":"{term in source language}","translated":"{translated term}","description":"{condiction to apply this translation, optional}"}`."""


@deprecated(
    "PreTranslatedContextSetResponseDTO is deprecated, use StoryContextSetResponseDTO instead.",
)
class PreTranslatedContextSetResponseDTO(PreTranslatedContextSetDTO, PromptedDTO):
    @classmethod
    def prompt(cls) -> str:
        """
        Returns the prompt for the DTO.
        """
        return """Provide improtant translation context note as format `{"context":[{"original":"{term in source language}","translated":"{translated term}","description":"{condiction to apply this translation, or basic information and persoality of a character. optional}"}]}`"""


def _context_filter(
    context: dict[str, "TermBankItemDTO"],
) -> dict[str, "TermBankItemDTO"]:
    """
    Filters the context to remove empty or unnecessary items.
    """
    return {k: v for k, v in context.items() if v.translated and (v.translated != k)}


class TermBankDTO(BaseModel):
    context: Annotated[dict[str, "TermBankItemDTO"], AfterValidator(_context_filter)]

    @classmethod
    def from_term_bank(cls, term_bank: TermBank) -> "TermBankDTO":
        """
        Converts a TermBank to a TermBankDTO.
        """
        return cls(
            context={
                k: TermBankItemDTO(**v.model_dump())
                for k, v in term_bank.context.items()
            }
        )

    def to_term_bank(self) -> TermBank:
        """
        Converts a TermBankDTO to a TermBank.
        """
        return TermBank(
            context={k: TermBankItem(**v.model_dump()) for k, v in self.context.items()}
        )

    def as_plain(self) -> str:
        """
        Converts a TermBankDTO to a plain string.
        """
        items = []
        for k, v in self.context.items():
            s = f"- {k}: {v.translated}"
            if v.description:
                s += f" ({v.description})"
            items.append(s)
        return "\n".join(items)


class TermBankItemDTO(TermBankItem):
    pass


class MetadataDTO(Metadata):
    @classmethod
    def from_metadata(cls, metadata: Metadata) -> "MetadataDTO":
        """
        Converts a MediaSetMetadata to a MediaSetMetadataDTO.
        """
        return cls(
            **metadata.model_dump(
                exclude={"characters"},
            ),
            characters=[
                CharacterInfoDTO.from_character_info(c) for c in metadata.characters
            ],
        )

    def to_plain(self) -> str:
        """
        Converts a MediaSetMetadataDTO to a plain dictionary.
        """

        characters = [f"- {','.join([i.name, *i.name_alt])}" for i in self.characters]

        return clear_indentation(f"""
        Title: {self.title} ({", ".join(self.title_alt)})
        {self.description}
        Characters:
        {"\n".join(characters)}
        """)


class CharacterInfoDTO(CharacterInfo):
    @classmethod
    def from_character_info(cls, character_info: CharacterInfo) -> "CharacterInfoDTO":
        """
        Converts a CharacterInfo to a CharacterInfoDTO.
        """
        return cls(**character_info.model_dump())


class SubtitleDTO(BaseModel):
    """
    DTO for subtitle dialogues
    """

    dialogues: "list[DialogueDTO]"

    @classmethod
    def from_subtitle(
        cls,
        dialogues: Iterable[Dialogue],
    ) -> "SubtitleDTO":
        """
        Converts a list of SubtitleDialogue to a SubtitleRequestDTO.
        """
        return cls(
            dialogues=[DialogueDTO.from_dialogue(i) for i in dialogues],
        )

    def apply_delta(
        self,
        delta: "SubtitleDeltaDTO",
    ) -> "SubtitleDTO":
        """
        Applies a delta to the subtitle dialogues.
        """
        updated_subtitles: List[DialogueDTO] = []
        for i in self.dialogues:
            if i.id in delta.dialogues:
                updated_subtitles.append(
                    DialogueDTO(
                        **i.model_dump(exclude={"content"}),
                        content=delta.dialogues[i.id],
                    )
                )
            else:
                updated_subtitles.append(i)

        return SubtitleDTO(
            dialogues=updated_subtitles,
        )

    def to_subtitle(self) -> list[Dialogue]:
        """
        Converts a SubtitleDTO to a list of SubtitleDialogue.
        """
        return [Dialogue(**i.model_dump()) for i in self.dialogues]

    def as_plain(self) -> str:
        """
        Converts a SubtitleDTO to a plain string.
        """
        items = [i.content for i in self.dialogues if i.content]

        return "\n".join(items)


class DialogueDTO(Dialogue):
    """
    DTO for subtitle dialogue
    """

    @classmethod
    def from_dialogue(
        cls,
        dialogue: Dialogue,
    ) -> "DialogueDTO":
        """
        Converts a SubtitleDialogue to a DialogueDTO.
        """
        return cls(**dialogue.model_dump())


class SubtitleDeltaDTO(BaseModel):
    """
    DTO for subtitle dialogues
    """

    dialogues: Dict[str, str]
