import asyncio
import logging
from typing import AsyncGenerator, Iterable, Optional, Type

from cost import CostTracker
from production_litellm import completion_cost, litellm
from pydantic import BaseModel, ValidationError
from setting import get_setting
from subtitle_types import (
    CharacterInfo,
    MediaSetMetadata,
    PreTranslatedContext,
    SubtitleDialogue,
)
from tqdm import tqdm

from .dto import (
    DialogueSetRequestDTO,
    DialogueSetResponseDTO,
    PreTranslatedContextSetDTO,
    dump_json,
    parse_json,
)

_logger = logging.getLogger(__name__)

litellm.enable_json_schema_validation = True
litellm.enable_cache = True


class FailedAfterRetries(Exception):
    """
    Custom exception for failed retries.
    """

    pass


async def _send_llm_request(
    *,
    content: str,
    instructions: Iterable[str],
    json_schema: Type[BaseModel],
    pretranslate: Optional[PreTranslatedContextSetDTO] = None,
) -> AsyncGenerator[str, None]:
    """
    Request translation from litellm.
    :param content: The content to translate.
    :param instructions: The instructions for the translation.
    :param progress_bar: Optional progress bar for tracking translation progress.
    :return: The translated text.
    """
    # Get model from environment variable or use default
    extra_prompt = get_setting().llm_extra_prompt
    model = get_setting().llm_model

    user_message = dump_json(
        {
            "subtitles": content,
        }
    )
    messages = [
        *[{"role": "system", "content": instruction} for instruction in instructions],
        {
            "role": "system",
            "content": "Response JSON does not need indentation and newline.",
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

    tokens = []
    async for part in response:  # type: ignore
        token = part.choices[0].delta.content or ""
        tokens.append(token)
        yield token

    cost = completion_cost(
        model=model,
        prompt=user_message + "".join([m["content"] for m in messages]),
        completion="".join(tokens),
    )
    CostTracker().add_cost(cost)


def _simple_sanity_check(
    original: Iterable[SubtitleDialogue], translated: Iterable[SubtitleDialogue]
) -> bool:
    """
    Perform a simple sanity check on the translation.
    :param original: The original text.
    :param translated: The translated text.
    :return: True if the translation passes the sanity check, False otherwise.
    """
    original_ids = {dialogue.id for dialogue in original}
    translated_ids = {dialogue.id for dialogue in translated}
    if original_ids != translated_ids:
        missing_ids = original_ids - translated_ids
        extra_ids = translated_ids - original_ids
        _logger.error(f"ID mismatch: missing: {missing_ids}, extra: {extra_ids}")
        return False
    return True


async def translate_dialogues(
    original: Iterable[SubtitleDialogue],
    target_language: str,
    pretranslate: Optional[Iterable[PreTranslatedContext]] = None,
    metadata: Optional[MediaSetMetadata] = None,
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
        progress_bar.total = sum(len(dialogue.content) for dialogue in original)

    system_message = f"""You are an experienced translator. Translate the text to {target_language}.
Important instructions:
1. Preserve all formatting exactly as they appear in the original content. Do not add or remove any formatting.
2. Output dialogues in the same order and the same ID as the original content.
3. Missing or incorrect IDs are not acceptable. Always return every ID.
4. It's not necessary to keep the original text in the translation as long as the meaning is preserved.
5. Any extra information, formatting, syntax, comments, or explanations in the output are not acceptable."""

    formatting_instruction = """Response example: { "subtitles": [{"id": 0, "content": "Hello"}, {"id": 1, "content": "World"}] }
You don't need to return the actor and style information, just return the content and id.
You don't have to keep the JSON string in ascii, you can use utf-8 encoding."""
    json_content = dump_json(DialogueSetRequestDTO.from_subtitle(original))
    if progress_bar is not None:
        progress_bar.total = len(json_content)

    messages = [
        system_message,
        formatting_instruction,
    ]
    if metadata:
        messages.append(matadata_prompt(metadata))

    translated: list[SubtitleDialogue] = []
    _pretranslate = (
        PreTranslatedContextSetDTO.from_contexts(pretranslate) if pretranslate else None
    )
    for retried in range(get_setting().llm_retry_times):
        try:
            chunks = []
            if progress_bar is not None:
                progress_bar.reset()
            async for chunk in _send_llm_request(
                content=json_content,
                instructions=messages,
                pretranslate=_pretranslate,
                json_schema=DialogueSetResponseDTO,
            ):
                chunks.append(chunk)
                if progress_bar is not None:
                    progress_bar.update(len(chunk))
            result = "".join(chunks)
            translated_dialogues = parse_json(
                DialogueSetResponseDTO, result
            ).to_subtitles()
            if not _simple_sanity_check(original, translated_dialogues):
                raise ValueError("Translation failed sanity check.")

            translated = translated_dialogues
            break

        except Exception as e:
            if isinstance(e, ValidationError):
                _logger.error(f"{e.error_count()} validation errors")
            else:
                _logger.error(f"Translation error: {e}")
            if retried < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retried
                )
                _logger.info(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e
    return translated


async def translate_context(
    original: Iterable[SubtitleDialogue],
    target_language: str,
    previous_translated: Optional[Iterable[PreTranslatedContext]] = None,
    metadata: Optional[MediaSetMetadata] = None,
    progress_bar: Optional[tqdm] = None,
) -> list[PreTranslatedContext]:
    """
    Extracts frequently used entities and their translations from the original text.
    :param original: The original text.
    :return: A list of important names and their translations.
    """
    system_message = f"""You are an experienced translator preparing translate the following anime, tv series, or movie subtitle text. Scan the text and extract important entity translation context from it before translation them into {target_language}

Important instructions:
1. Identify rare words that appear frequently in the text.
2. Always provide translations in {target_language}.
4. Only include actual rare terms of entities. Common nouns, sentences or other text that are commonly used outside the context are not allowed.
5. Character name should always be noted and translate into {target_language}.
6. Duplication not allowed."""

    formatting_instruction = (
        """Response example: `{ "context": [{"original": "Hello", "translated": "你好"}, {"original": "SEKAI", "translated": "世界", "description": "The same as world."}] }`
Be aware that the description field is optional, use it only when necessary.
`original`: term in source language, `translated`: term in target language ("""
        + target_language
        + """).
You don't have to keep the JSON string in ascii, you can use utf-8 encoding."""
    )

    messages = [system_message, formatting_instruction]

    if metadata:
        messages.append(matadata_prompt(metadata))

    if previous_translated:
        messages.append(
            f"Here are previous context note you take. You may overwrite them by having the same `original` field. DO NOT re-output them:\n {dump_json(PreTranslatedContextSetDTO.from_contexts(previous_translated))}"
        )

    contexts: list[PreTranslatedContext] = []
    result = ""

    for retry in range(get_setting().llm_retry_times):
        try:
            if progress_bar is not None:
                progress_bar.reset()
            chunks = []
            async for chunk in _send_llm_request(
                content="\n".join([dialogue.content for dialogue in original]),
                instructions=messages,
                json_schema=PreTranslatedContextSetDTO,
            ):
                chunks.append(chunk)
                if progress_bar is not None:
                    progress_bar.update(len(chunk))
            result = "".join(chunks)
            if not result:
                raise ValueError("Empty response from LLM")
            contexts = parse_json(PreTranslatedContextSetDTO, result).to_contexts()
            break  # Exit the retry loop if successful

        except Exception as e:
            if isinstance(e, ValidationError):
                _logger.error(f"{e.error_count()} validation errors")
            else:
                _logger.error(f"Translation error: {e}")
            if retry < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retry
                )
                _logger.info(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e

    return contexts


async def refine_context(
    target_language: str,
    contexts: Iterable[PreTranslatedContext],
    metadata: Optional[MediaSetMetadata] = None,
    progress_bar: Optional[tqdm] = None,
) -> list[PreTranslatedContext]:
    """
    Refine the context before dialogue translation.
    :param target_language: The target language for translation.
    :param contexts: The original context.
    :param metadata: The metadata for the media set.
    :return: The refined context.
    """

    system_message = f"""You are an experienced translator preparing translate the following anime, tv series, or movie subtitle text. Refine the context note before translation them into {target_language}

        Important instructions:
        1. Review the context note.
        2. Make sure all translations in {target_language} are correct.
        3. Keep it concise, remove common terms.
        4. Return whole note after refinement."""

    formatting_instruction = (
        """Response example: `{ "context": [{"original": "Hello", "translated": "你好"}, {"original": "SEKAI", "translated": "世界", "description": "The same as world."}] }`
Be aware that the description field is optional, use it only when necessary.
You don't have to keep the JSON string in ascii, you can use utf-8 encoding.
`original`: term in source language, `translated`: term in target language ("""
        + target_language
        + """).
Return only the context note, no other text is allowed."""
    )

    messages = [system_message, formatting_instruction]

    if metadata:
        messages.append(matadata_prompt(metadata))

    json_content = dump_json(PreTranslatedContextSetDTO.from_contexts(contexts))
    if progress_bar is not None:
        progress_bar.total = len(json_content)

    refined_contexts = []
    for retry in range(get_setting().llm_retry_times):
        chunks = []
        if progress_bar is not None:
            progress_bar.reset()
        try:
            async for chunk in _send_llm_request(
                content=json_content,
                instructions=messages,
                json_schema=PreTranslatedContextSetDTO,
            ):
                chunks.append(chunk)
                if progress_bar is not None:
                    progress_bar.update(len(chunk))

            result = "".join(chunks)
            if not result:
                raise ValueError("Empty response from LLM")
            refined_contexts = parse_json(
                PreTranslatedContextSetDTO, result
            ).to_contexts()
            break
        except Exception as e:
            if isinstance(e, ValidationError):
                _logger.error(f"{e.error_count()} validation errors")
            else:
                _logger.error(f"Translation error: {e}")
            if retry < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retry
                )
                _logger.info(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e
    return refined_contexts


def matadata_prompt(metadata: MediaSetMetadata) -> str:
    title_alt = (
        f", also called {', '.join(metadata.title_alt)}" if metadata.title_alt else ""
    )

    return f"""Here are some basic information about this story:
    Title: {metadata.title}{title_alt}
    Description: {metadata.description}

    Main characters:
    {"\n".join([character_prompt(character) for character in metadata.characters])}
    """


def character_prompt(chara: CharacterInfo) -> str:
    name_alt = f", also called {', '.join(chara.name_alt)}" if chara.name_alt else ""
    return f"""{chara.name}{name_alt}. Gender is {chara.gender}"""
