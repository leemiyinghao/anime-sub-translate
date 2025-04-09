import os, asyncio, re, json, logging
from typing import Optional, Iterable, AsyncGenerator, Type, List, Annotated, TypeVar

from pydantic_core.core_schema import json_schema
from subtitle_types import RichSubtitleDialogue, SubtitleDialogue, PreTranslatedContext
import litellm
from tqdm import tqdm
from pydantic import BaseModel, BeforeValidator, ValidationError

RETRY_TIMES = 5

_logger = logging.getLogger(__name__)

litellm.enable_json_schema_validation = True
litellm.enable_cache = True


class FailedAfterRetries(Exception):
    """
    Custom exception for failed retries.
    """

    pass


T = TypeVar("T", bound=BaseModel)


def obj_or_json(model: Type[T], obj: T | str) -> T:
    """
    Converts a string to a JSON object or returns the object as is.
    Aiming to solve double-serialization issue experienced with Gemini 2.0 Flash.
    """
    if isinstance(obj, str):
        return model.model_validate_json(obj)
    return obj


class SubtitleDialogueDTO(BaseModel):
    """
    DTO for subtitle dialogue.
    """

    id: int
    content: str


class DialogueResponseDTO(BaseModel):
    """
    Response DTO for dialogues translation.
    """

    subtitles: Annotated[
        List[SubtitleDialogueDTO],
        BeforeValidator(lambda v: [obj_or_json(SubtitleDialogueDTO, i) for i in v]),
    ]


class PreTranslatedContextDTO(BaseModel):
    """
    DTO for pre-translated context.
    """

    original: str
    translated: str
    description: Optional[str] = None


class ContextResponseDTO(BaseModel):
    """
    Response DTO for context translation.
    """

    context: Annotated[
        List[PreTranslatedContextDTO],
        BeforeValidator(lambda v: [obj_or_json(PreTranslatedContextDTO, i) for i in v]),
    ]


def dump_json(obj: object) -> str:
    """
    Dumps a Python object to a JSON string.
    :param obj: The object to dump.
    :return: The JSON string.
    """
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


async def _send_llm_request(
    *,
    content: str,
    instructions: Iterable[str],
    json_schema: Type[BaseModel],
    pretranslate: Optional[Iterable[PreTranslatedContext]] = None,
) -> AsyncGenerator[str, None]:
    """
    Request translation from litellm.
    :param content: The content to translate.
    :param instructions: The instructions for the translation.
    :param progress_bar: Optional progress bar for tracking translation progress.
    :return: The translated text.
    """
    # Get model from environment variable or use default
    extra_prompt = os.environ.get("LLM_EXTRA_PROMPT", "")
    model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")

    user_message = dump_json(
        {
            "subtitles": content,
        }
    )
    messages = [
        {"role": "system", "content": "\n".join(instructions)},
        {
            "role": "system",
            "content": "Respect JSON schema.",
        },
    ]
    if pretranslate:
        json_pretranslate = dump_json(
            pretranslate,
        )
        messages.append(
            {
                "role": "system",
                "content": f"Use the following context for names and terms consistently:\n {json_pretranslate}",
            },
        )
    if extra_prompt:
        messages.append({"role": "system", "content": extra_prompt})

    messages.append({"role": "user", "content": user_message})

    response = await litellm.acompletion(
        n=1,
        model=model,
        messages=messages,
        stream=True,
        response_format={
            "type": "json_schema",
            "schema": json_schema.model_json_schema(),
            "strict": True,
        },
    )

    async for part in response:  # type: ignore
        token = part.choices[0].delta.content or ""
        yield token


def _simple_sanity_check(
    original: Iterable[RichSubtitleDialogue], translated: Iterable[SubtitleDialogue]
) -> bool:
    """
    Perform a simple sanity check on the translation.
    :param original: The original text.
    :param translated: The translated text.
    :return: True if the translation passes the sanity check, False otherwise.
    """
    original_ids = {dialogue["id"] for dialogue in original}
    translated_ids = {dialogue["id"] for dialogue in translated}
    if original_ids != translated_ids:
        missing_ids = original_ids - translated_ids
        extra_ids = translated_ids - original_ids
        _logger.error(f"ID mismatch: missing: {missing_ids}, extra: {extra_ids}")
        return False
    return True


async def translate_dialouges(
    original: Iterable[RichSubtitleDialogue],
    target_language: str,
    pretranslate: Optional[Iterable[PreTranslatedContext]] = None,
    progress_bar: Optional[tqdm] = None,
) -> Iterable[SubtitleDialogue]:
    """
    Translates the given text to the target language using litellm.
    :param content: The content to translate.
    :param target_language: The target language for translation.
    :param pretranslate: Optional pre-translation important names.
    :return: The translated text.
    """

    if progress_bar is not None:
        progress_bar.total = sum(len(dialogue["content"]) for dialogue in original)

    system_message = f"""You are an experienced translator. Translate the text to {target_language}.
Important instructions:
1. Preserve all formatting exactly as they appear in the original content. Do not add or remove any formatting.
2. Output dialogues in the same order and the same ID as the original content.
3. Missing or incorrect IDs are not acceptable.
4. It's not necessary to keep the original text in the translation as long as the meaning is preserved."""

    formatting_instruction = """Response example: { "subtitles": [{"id": 0, "content": "Hello"}, {"id": 1, "content": "World"}] }
You don't need to return the actor and style information, just return the content and id.
You don't have to keep the JSON string in ascii, you can use utf-8 encoding."""

    json_content = dump_json(
        [
            {
                "id": dialogue["id"],
                "content": dialogue["content"],
            }
            for dialogue in original
        ]
    )

    translated: list[SubtitleDialogue] = []
    for retry in range(RETRY_TIMES):
        try:
            chunks = []
            if progress_bar is not None:
                progress_bar.reset()
            async for chunk in _send_llm_request(
                content=json_content,
                instructions=[system_message, formatting_instruction],
                pretranslate=pretranslate,
                json_schema=DialogueResponseDTO,
            ):
                chunks.append(chunk)
                if progress_bar is not None:
                    progress_bar.update(len(chunk))
            result = "".join(chunks)
            chunks = [
                SubtitleDialogue(
                    id=dialogue.id,
                    # LLMs have a tendency to over-escape backslashes.
                    content=re.sub(r"\\+", "\\\\", dialogue.content),
                )
                for dialogue in parse_json(DialogueResponseDTO, result).subtitles
            ]
            if not _simple_sanity_check(original, chunks):
                raise ValueError("Translation failed sanity check.")

            translated = chunks
            break

        except Exception as e:
            if isinstance(e, ValidationError):
                _logger.error(f"{e.error_count()} validation errors")
            else:
                _logger.error(f"Translation error: {e}")
            if retry < RETRY_TIMES - 1:
                after = min(2**retry, 60)
                _logger.info(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e
    return translated


async def translate_context(
    original: Iterable[RichSubtitleDialogue],
    target_language: str,
    previous_translated: Optional[Iterable[PreTranslatedContext]] = None,
    progress_bar: Optional[tqdm] = None,
) -> list[PreTranslatedContext]:
    """
    Extracts frequently used entities and their translations from the original text.
    :param original: The original text.
    :return: A list of important names and their translations.
    """
    system_message = f"""You are an experienced translator preparing translate the following anime, tv series, or movie subtitle text. Scan the text and extract important entity translation context from it before translation them into {target_language}

Important instructions:
1. Identify names of people, places, organizations, and other proper entities or nouns that appear frequently in the text.
2. Provide translations for these names if appropriate in the target language.
3. For names that should not be translated, indicate they should remain as is.
4. Only include actual names of entities, not common nouns, sentences or other text that are commonly used outside the context."""

    formatting_instruction = """Response example: `{ "context": [{"original": "Hello", "translated": "你好"}, {"original": "SEKAI", "translated": "世界", "description": "The same as world."}] }`
Be aware that the description field is optional, use it only when necessary.
You don't have to keep the JSON string in ascii, you can use utf-8 encoding."""

    messages = [system_message, formatting_instruction]
    if previous_translated:
        messages.append(
            f"Here are previous context note you take. Reuse and output them, but DO NOT EDIT or REMOVE any of them:\n {dump_json(previous_translated)}"
        )

    contexts: list[PreTranslatedContext] = []
    result = ""

    for retry in range(RETRY_TIMES):
        try:
            if progress_bar is not None:
                progress_bar.reset()
            chunks = []
            async for chunk in _send_llm_request(
                content="\n".join([dialogue["content"] for dialogue in original]),
                instructions=messages,
                json_schema=ContextResponseDTO,
            ):
                chunks.append(chunk)
                if progress_bar is not None:
                    progress_bar.update(len(chunk))
            result = "".join(chunks)
            if not result:
                raise ValueError("Empty response from LLM")
            contexts = [
                PreTranslatedContext(
                    original=dialogue.original,
                    translated=dialogue.translated,
                    description=dialogue.description,
                )
                for dialogue in parse_json(ContextResponseDTO, result).context
            ]
            break  # Exit the retry loop if successful

        except Exception as e:
            if isinstance(e, ValidationError):
                _logger.error(f"{e.error_count()} validation errors")
            else:
                _logger.error(f"Translation error: {e}")
            if retry < RETRY_TIMES - 1:
                after = min(2**retry, 60)
                _logger.info(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e

    return contexts
