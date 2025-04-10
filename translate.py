import asyncio
import logging
import os
import re
from itertools import batched
from typing import Iterable, Optional

from tqdm.auto import tqdm

from anilist import search_mediaset_metadata
from format import parse_subtitle_file
from format.format import SubtitleFormat
from llm import translate_context, translate_dialogues
from setting import get_setting
from store import (
    load_media_set_metadata,
    load_pre_translate_store,
    save_media_set_metadata,
    save_pre_translate_store,
)
from subtitle_types import MediaSetMetadata, PreTranslatedContext, SubtitleDialogue
from utils import (
    chunk_dialogues,
    find_files_from_path,
    read_subtitle_file,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_language_postfix(target_language: str) -> str:
    """
    Gets the language postfix from setting or defaults to the target language.
    """
    return get_setting().language_postfix or target_language


def create_output_file_path(subtitle_file: str, language_postfix: str) -> str:
    """
    Creates the output file path for the translated subtitle file.
    """
    base_name, ext = os.path.splitext(subtitle_file)
    output_file = f"{base_name}.{language_postfix}{ext}"
    output_dir = os.path.dirname(subtitle_file)
    return os.path.join(output_dir, output_file)


def get_output_path(subtitle_file: str, target_language: str) -> str:
    """
    Generates the output path for the translated subtitle file.
    """
    language_postfix = get_language_postfix(target_language)
    return create_output_file_path(subtitle_file, language_postfix)


def write_translated_subtitle(translated_content: str, output_path: str) -> None:
    """
    Writes the translated content to a new subtitle file with the language postfix.
    """
    try:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(translated_content.strip() + "\n")
    except Exception as e:
        logging.error(f"Error writing translated subtitle to {output_path}: {e}")


async def translate_file(
    subtitle_content: SubtitleFormat,
    target_language: str,
    pre_translated_context: Iterable[PreTranslatedContext],
    metadata: Optional[MediaSetMetadata] = None,
) -> SubtitleFormat:
    """
    Translates the subtitle content in chunks.
    """
    # Characters per chunk (adjust based on token limits)
    #
    # We use characters instead of tokens, because each model has
    # different tokenization process, and it's fine to assume tokens
    # will be less than characters
    #
    # Since we are translating, we can assume that the output tokens
    # will be similar to the input tokens.
    max_chunk_size = min(get_setting().max_output_token, get_setting().max_input_token)
    chunks = chunk_dialogues(subtitle_content.dialogues(), max_chunk_size)
    concurrency = get_setting().concurrency
    logger.info(f"Total chunks: {len(chunks)}")

    translated_dialogues = []
    # group chunks by concurrency
    for chunk_group in batched(enumerate(chunks), concurrency):
        tasks = []
        for idx, dialogue_chunk in chunk_group:
            progress_bar = None
            if get_setting().verbose:
                progress_bar = tqdm(
                    desc=f"Translating chunk {idx + 1}/{len(chunks)}",
                    position=idx + 1,
                    total=len(dialogue_chunk),
                )
            tasks.append(
                translate_dialogues(
                    original=dialogue_chunk,
                    target_language=target_language,
                    pretranslate=pre_translated_context,
                    metadata=metadata,
                    progress_bar=progress_bar,
                )
            )
        translated_chunk_group: list[list[SubtitleDialogue]] = await asyncio.gather(
            *tasks
        )
        if get_setting().verbose:
            logger.info("Translated chunk:")
            for idx, dialogue in enumerate(
                [dialogue for _chunk in translated_chunk_group for dialogue in _chunk]
            ):
                logger.info(f"  {idx}: {dialogue.content}")
        translated_dialogues.extend(translated_chunk_group)
    for translated_chunk in translated_dialogues:
        subtitle_content.update(translated_chunk)

    return subtitle_content


async def prepare_context(
    subtitle_contents: Iterable[SubtitleFormat],
    target_language: str,
    metadata: Optional[MediaSetMetadata] = None,
) -> list[PreTranslatedContext]:
    """
    Prepares the translation by translating the context.
    """

    # Characters per chunk (adjust based on token limits)
    #
    # We use characters instead of tokens, because each model has
    # different tokenization process, and it's fine to assume tokens
    # will be less than characters
    #
    # Since we are only extracting context, output tokens will be far
    # less than input tokens. The output tokens is ignorable.
    max_chunk_size = get_setting().max_input_token
    dialogues: list[SubtitleDialogue] = []
    for subtitle_content in subtitle_contents:
        dialogues.extend(subtitle_content.dialogues())

    # dedupe dialogues since we are only using it to find context
    dialogues = [
        d for d in {dialogue.content: dialogue for dialogue in dialogues}.values()
    ]

    chunks = chunk_dialogues(dialogues, max_chunk_size)

    pre_translated_context = []
    for idx, dialogue_chunk in enumerate(chunks):
        progress_bar = tqdm(
            desc=f"Pre-translating context {idx + 1}/{len(chunks)}",
        )
        context = await translate_context(
            original=dialogue_chunk,
            target_language=target_language,
            progress_bar=progress_bar,
            previous_translated=pre_translated_context,
            metadata=metadata,
        )
        pre_translated_context = list(context)
        # deduplicate context by original
        pre_translated_context = [
            context
            for _, context in {
                context.original: context for context in pre_translated_context
            }.items()
        ]
        if get_setting().verbose:
            logger.info("Update context:")
            for idx, context in enumerate(pre_translated_context):
                logger.info(f"  {idx}: {context.original} -> {context.translated}")

    return pre_translated_context


def prepare_metadata(
    path: str,
) -> Optional[MediaSetMetadata]:
    # resolve leaf directory name from path
    dir_name = os.path.abspath(path)
    dir_name = os.path.dirname(dir_name)
    dir_name = os.path.basename(dir_name)

    title = dir_name.replace("_", " ").replace("-", " ")  # replace special characters
    title = re.sub(
        r"\[[^\]]+\]|\s+", "", title
    ).strip()  # remove brackets and extra spaces

    # search for metadata
    metadata = search_mediaset_metadata(title)
    return metadata


def translate(path: str, target_language: str) -> None:
    """
    Translates the subtitles in the given file to the target language.
        :param path: Path to the subtitle files. File can be .srt, .ssa, .ass.
        :param target_language: Target language for translation.
        :param output_path: Path to save the translated subtitles.
    """

    try:
        subtitle_paths = find_files_from_path(
            path, get_language_postfix(target_language)
        )
        if not subtitle_paths:
            logger.error(f"No subtitles found in {subtitle_paths}")
            return

        # read all files
        subtitle_contents = []
        for subtitle_path in subtitle_paths:
            content = read_subtitle_file(subtitle_path)
            subtitle_contents.append(content)

        subtitle_formats = [parse_subtitle_file(file) for file in subtitle_paths]

        # mediaset metadata
        metadata = None
        if stored := load_media_set_metadata(path):
            metadata = stored
        else:
            metadata = prepare_metadata(path)
            if metadata:
                save_media_set_metadata(path, metadata)

        if metadata:
            # print metadata
            logger.info("Metadata:")
            logger.info(f"  Title: {metadata.title} ({','.join(metadata.title_alt)})")
            logger.info(f"  {metadata.description}")
            logger.info(f"  Characters:")
            for character in metadata.characters:
                logger.info(
                    f"    {character.name}, {character.gender} ({','.join(character.name_alt)})"
                )

        # pre-translate context
        pre_translate_context = None
        if stored := load_pre_translate_store(path):
            pre_translate_context = stored
        else:
            pre_translate_context = asyncio.run(
                prepare_context(subtitle_formats, target_language, metadata=metadata)
            )
            save_pre_translate_store(path, pre_translate_context)

        # Print pre-translate context and metadata
        logger.info("pre-translate context:")
        for context in pre_translate_context:
            logger.info(
                f"  {context.original} -> {context.translated} ({context.description})"
            )

        for subtitle_path, subtitle_format in tqdm(
            zip(subtitle_paths, subtitle_formats, strict=False),
            desc="Translate files",
            unit="file",
            total=len(subtitle_paths),
        ):
            output_path = get_output_path(subtitle_path, target_language)
            if os.path.exists(output_path):
                logger.info(f"Output file {output_path} already exists.")
                continue

            translated_content = asyncio.run(
                translate_file(
                    subtitle_format,
                    target_language,
                    pre_translate_context,
                    metadata=metadata,
                )
            )

            # replace Title line in support format like ASS/SSA
            translated_content.update_title(f"{target_language} (AI Translated)")

            write_translated_subtitle(translated_content.as_str(), output_path)
            logger.info(f"Translated content wrote: {output_path[-60:]}")

        logging.info(
            f"All subtitles translated successfully ({len(subtitle_paths)} files)"
        )

    except Exception as e:
        logging.error(f"Error translating subtitles: {e}")
        raise
