import asyncio
from typing import AsyncGenerator, Iterable, Optional, Type

from cost import CostTracker
from logger import logger
from production_litellm import completion_cost, litellm
from progress import current_progress
from setting import get_setting
from subtitle_types import (
    CharacterInfo,
    MediaSetMetadata,
    PreTranslatedContext,
    SubtitleDialogue,
)

from .dto import (
    DialogueSetRequestDTO,
    DialogueSetResponseDTO,
    PreTranslatedContextSetDTO,
    PreTranslatedContextSetResponseDTO,
    PromptedDTO,
    dump_json,
    parse_json,
)

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
    action: str,
    json_schema: Type[PromptedDTO],
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

    pretranslate_message = []
    if pretranslate:
        plain_pretranslate = "\n".join(
            [
                f"{context.original} -> {context.translated} ({context.description or ''})"
                for context in pretranslate.context
            ]
        )
        pretranslate_message.append(
            {
                "role": "system",
                "content": f"Use the following context for names and terms consistently:\n {plain_pretranslate}",
            },
        )

    extra_prompts = []
    if extra_prompt:
        extra_prompts.append(
            {
                "role": "system",
                "content": extra_prompt,
            }
        )

    messages = [
        {
            "role": "system",
            "content": "Ensure using term that is correct and fit the style of story when translating.",
        },
        *[{"role": "system", "content": instruction} for instruction in instructions],
        *pretranslate_message,
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": f"{json_schema.prompt()}",
        },
        {
            "role": "system",
            "content": "Response JSON does not need indentation and newline.",
        },
        {
            "role": "user",
            "content": action,
        },
    ]

    response = await litellm.acompletion(
        n=1,
        model=model,
        messages=messages,
        stream=True,
        response_format={"type": "json_object"},
    )

    tokens = []
    async for part in response:  # type: ignore
        token = part.choices[0].delta.content or ""
        tokens.append(token)
        yield token

    try:
        cost = completion_cost(
            model=model,
            prompt="".join([m["content"] for m in messages]),
            completion="".join(tokens),
        )
        CostTracker().add_cost(cost)
    except:
        # litellm may not support this model
        pass


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
        logger.warning(f"ID mismatch: missing: {missing_ids}, extra: {extra_ids}")
        return False
    return True


async def translate_dialogues(
    original: Iterable[SubtitleDialogue],
    target_language: str,
    pretranslate: Optional[Iterable[PreTranslatedContext]] = None,
    metadata: Optional[MediaSetMetadata] = None,
) -> Iterable[SubtitleDialogue]:
    """
    Translates the given text to the target language using litellm.
    :param content: The content to translate.
    :param target_language: The target language for translation.
    :param pretranslate: Optional pre-translation important names.
    :return: The translated text.
    """

    system_message = f"""You are an experienced translator. Translating the text to {target_language}.
Important instructions:
1. Consider fluency, meaning, coherence, style, context, and character personality.
2. Output dialogues in the same ID as the original content as possible.
3. Missing or incorrect IDs are not acceptable. Do not create new ID.
4. Do not keep the original text in translated result.
5. Any extra comments or explanations in the result are not acceptable."""

    json_content = dump_json(DialogueSetRequestDTO.from_subtitle(original))

    messages = [
        system_message,
    ]
    if metadata:
        messages.append(matadata_prompt(metadata))

    translated: list[SubtitleDialogue] = []
    _pretranslate = (
        PreTranslatedContextSetDTO.from_contexts(pretranslate) if pretranslate else None
    )

    current_progress().set_total(len(json_content))
    for retried in range(get_setting().llm_retry_times):
        try:
            current_progress().reset()
            chunks = []
            async for chunk in _send_llm_request(
                action="Provide translated result.",
                content=f"Subtitle in source language: {json_content}",
                instructions=messages,
                pretranslate=_pretranslate,
                json_schema=DialogueSetResponseDTO,
            ):
                chunks.append(chunk)
                current_progress().update(len(chunk))
            result = "".join(chunks)
            logger.debug(f"LLM response:\n{result}")
            translated_dialogues = parse_json(
                DialogueSetResponseDTO, result
            ).to_subtitles()
            if not _simple_sanity_check(original, translated_dialogues):
                raise ValueError("Translation failed sanity check.")
            translated = translated_dialogues
            current_progress().finish()
            break

        except Exception as e:
            logger.warning(f"Translation error: {e}")
            if retried < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retried
                )
                logger.warning(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e
    return translated


async def translate_context(
    original: Iterable[SubtitleDialogue],
    target_language: str,
    previous_translated: Optional[Iterable[PreTranslatedContext]] = None,
    metadata: Optional[MediaSetMetadata] = None,
) -> list[PreTranslatedContext]:
    """
    Extracts frequently used entities and their translations from the original text.
    :param original: The original text.
    :return: A list of important names and their translations.
    """
    system_message = f"""You are an experienced translator preparing translate the following anime, tv series, or movie subtitle text. Scan the text and extract important entity translation context from it before translation them into {target_language}, this will be used to provide consistent translation in the future.

Important instructions:
1. Identify rare and improtant terms that need to be translated consistently.
2. Common nouns, sentences or other text that are commonly used outside the context are not allowed.
3. Character name are always important.
4. Duplication or over-detailed are not allowed."""

    messages = [system_message]

    if metadata:
        messages.append(matadata_prompt(metadata))

    if previous_translated:
        messages.append(
            f"Here are previous context note you take. You may overwrite them by having the same `original` field. DO NOT re-output them:\n {dump_json(PreTranslatedContextSetDTO.from_contexts(previous_translated))}"
        )

    contexts: list[PreTranslatedContext] = []
    content = "Subtitle in source language:\n" + "\n".join(
        [dialogue.content for dialogue in original]
    )
    result = ""

    current_progress().set_total(len(content))

    for retry in range(get_setting().llm_retry_times):
        try:
            current_progress().reset()
            chunks = []
            async for chunk in _send_llm_request(
                action="Understand the story and provide context note that can help you translate the text consistently in the future.",
                content=content,
                instructions=messages,
                json_schema=PreTranslatedContextSetResponseDTO,
            ):
                chunks.append(chunk)
                current_progress().update(len(chunk))
            result = "".join(chunks)
            if not result:
                raise ValueError("Empty response from LLM")
            contexts = parse_json(PreTranslatedContextSetDTO, result).to_contexts()
            current_progress().finish()
            break  # Exit the retry loop if successful

        except Exception as e:
            logger.warning(f"Translation error: {e}")
            if retry < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retry
                )
                logger.warning(f"Retrying after {after} seconds...")
                await asyncio.sleep(after)
                continue
            raise FailedAfterRetries() from e

    return contexts


async def refine_context(
    target_language: str,
    contexts: Iterable[PreTranslatedContext],
    metadata: Optional[MediaSetMetadata] = None,
) -> list[PreTranslatedContext]:
    """
    Refine the context before dialogue translation.
    :param target_language: The target language for translation.
    :param contexts: The original context.
    :param metadata: The metadata for the media set.
    :return: The refined context.
    """

    system_message = f"""You are an experienced translator preparing translate the following anime, tv series, or movie subtitle text. Refine the context note before translation them into {target_language}, this will be used to provide consistent translation in the future.
Important instructions:
1. Review the context note.
2. Make sure all translations are meaningfully correct.
3. Make sure all translations are fit the style of story.
4. Keep context note concise, remove common terms or unnecessary information."""

    messages = [system_message]

    if metadata:
        messages.append(matadata_prompt(metadata))

    json_content = dump_json(PreTranslatedContextSetDTO.from_contexts(contexts))

    current_progress().set_total(len(json_content))

    refined_contexts = []
    for retry in range(get_setting().llm_retry_times):
        chunks = []
        progress_bar = current_progress()
        try:
            async for chunk in _send_llm_request(
                action=f"Provide refined context note (from source language to {target_language}) that can help me translate the text consistently in the future.",
                content=json_content,
                instructions=messages,
                json_schema=PreTranslatedContextSetResponseDTO,
            ):
                chunks.append(chunk)
                progress_bar.update(len(chunk))

            result = "".join(chunks)
            if not result:
                raise ValueError("Empty response from LLM")
            refined_contexts = parse_json(
                PreTranslatedContextSetDTO, result
            ).to_contexts()
            current_progress().finish()
            break
        except Exception as e:
            logger.warning(f"Translation error: {e}")
            if retry < get_setting().llm_retry_times - 1:
                after = get_setting().llm_retry_delay * (
                    get_setting().llm_retry_backoff ** retry
                )
                logger.warning(f"Retrying after {after} seconds...")
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
