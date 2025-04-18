import asyncio
import os
import re
from collections import OrderedDict
from dataclasses import dataclass
from functools import cached_property
from itertools import batched
from typing import Awaitable, Callable, Iterable, Optional, TypeVar

from tqdm.auto import tqdm

from anilist import search_mediaset_metadata
from format import parse_subtitle_file
from format.format import SubtitleFormat
from llm import refine_context, translate_context, translate_dialogues
from logger import logger
from progress import current_progress
from setting import get_setting
from speedometer import Speedometer
from store import (
    load_media_set_metadata,
    load_pre_translate_store,
    save_media_set_metadata,
    save_pre_translate_store,
)
from subtitle_types import Dialogue, Metadata, TermBank
from utils import (
    chunk_dialogues,
    dialogue_remap_id,
    dialogue_remap_id_reverse,
    find_files_from_path,
)

F = TypeVar("F", bound=Callable)


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
        logger.error(f"Error writing translated subtitle to {output_path}: {e}")


async def translate_file(
    subtitle_content: SubtitleFormat,
    target_language: str,
    term_bank: Optional[TermBank] = None,
    metadata: Optional[Metadata] = None,
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
    # remap dialogues ids to reduce token usage
    chunks, id_maps = tuple(zip(*[dialogue_remap_id(chunk) for chunk in chunks]))

    chunks = [(chunk, current_progress().sub_progress()) for chunk in chunks]
    concurrency = get_setting().concurrency

    translated_dialogues = []
    # group chunks by concurrency
    for chunk_group in batched(enumerate(chunks), concurrency):
        tasks = []
        for idx, (dialogue_chunk, prog) in chunk_group:
            tasks.append(
                prog.async_monitor(
                    translate_dialogues,
                    original=dialogue_chunk,
                    target_language=target_language,
                    pretranslate=term_bank,
                    metadata=metadata,
                )
            )
        translated_chunk_group: list[list[Dialogue]] = await asyncio.gather(*tasks)
        if get_setting().debug:
            logger.debug("Translated chunk:")
            for idx, dialogue in enumerate(
                [dialogue for _chunk in translated_chunk_group for dialogue in _chunk]
            ):
                logger.debug(f"  {idx}: {dialogue.content}")
        translated_dialogues.extend(translated_chunk_group)
    for translated_chunk, id_map in zip(translated_dialogues, id_maps):
        # reverse remap dialogues ids
        translated_chunk = dialogue_remap_id_reverse(translated_chunk, id_map)
        subtitle_content.update(translated_chunk)

    return subtitle_content


async def _prepare_context(
    subtitle_contents: Iterable[SubtitleFormat],
    target_language: str,
    metadata: Optional[Metadata] = None,
    term_bank: Optional[TermBank] = None,
) -> TermBank:
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
    dialogues: list[Dialogue] = []
    for subtitle_content in subtitle_contents:
        dialogues.extend(subtitle_content.dialogues())

    # dedupe dialogues since we are only using it to find context, but keep the order
    dialogue_map = OrderedDict()
    for d in dialogues:
        dialogue_map[d.content] = d
    dialogues = [dialogue for dialogue in dialogue_map.values()]

    chunks = chunk_dialogues(dialogues, max_chunk_size)
    chunks = [
        (chunk, current_progress().sub_progress()) for chunk in chunks
    ]  # add progress bar to each chunk
    refine_progress = current_progress().sub_progress()

    _term_bank = term_bank or TermBank(context={})
    concurrency = get_setting().concurrency  # Get concurrency setting
    per_response_limit = (
        int(get_setting().max_input_token / len(chunks))
        if chunks
        else get_setting().max_input_token
    )
    for chunk_group in batched(chunks, concurrency):  # Batch chunks by concurrency
        tasks = []
        for dialogue_chunk, prog in chunk_group:
            tasks.append(
                prog.async_monitor(
                    translate_context,
                    original=dialogue_chunk,
                    target_language=target_language,
                    metadata=metadata,
                    limit=per_response_limit,
                )
            )
        new_contexts = await asyncio.gather(*tasks)

        for context in new_contexts:
            _term_bank.update(context)

        if get_setting().debug:
            logger.debug("Update context:")
            for k, context in _term_bank.context.items():
                logger.debug(f"  {k} -> {context.translated} ({context.description})")

    # refine context
    _term_bank = await refine_progress.async_monitor(
        refine_context,
        contexts=_term_bank,
        target_language=target_language,
        metadata=metadata,
        limit=get_setting().pre_translate_size,
    )

    return _term_bank


async def prepare_metadata(
    path: str,
) -> Optional[Metadata]:
    # resolve leaf directory name from path
    dir_name = os.path.abspath(path)
    if os.path.isfile(dir_name):
        dir_name = os.path.dirname(dir_name)
    dir_name = os.path.basename(dir_name)

    title = dir_name.replace("_", " ").replace("-", " ")  # replace special characters
    title = re.sub(
        r"\[[^\]]+\]|\s+", "", title
    ).strip()  # remove brackets and extra spaces

    # search for metadata
    metadata = await search_mediaset_metadata(title)
    return metadata


@dataclass
class TaskParameter:
    base_path: str
    target_language: str
    metadata: Optional[Metadata] = None
    term_bank: Optional[TermBank] = None
    set_description: Optional[Callable[[str], None]] = None

    @cached_property
    def subtitle_paths(self) -> list[str]:
        """
        Returns the list of subtitle paths in the base path.
        """
        return find_files_from_path(
            self.base_path,
            get_language_postfix(self.target_language),
            match_postfix=get_setting().sub_postfix,
        )

    def update(self, **kwargs) -> "TaskParameter":
        """
        Return a new TaskParameter with updated values.
        """
        new_param = TaskParameter(
            base_path=self.base_path,
            target_language=self.target_language,
            metadata=self.metadata,
            term_bank=self.term_bank,
            set_description=self.set_description,
        )
        for key, value in kwargs.items():
            setattr(new_param, key, value)
        return new_param


async def task_prepare_context(
    param: TaskParameter,
) -> TaskParameter:
    """
    Prepares the translation by translating the context.
    """
    term_bank = param.term_bank or TermBank(context={})
    param.set_description("Preparing context note") if param.set_description else None
    if not term_bank and (stored := load_pre_translate_store(param.base_path)):
        term_bank = stored

    if not term_bank:
        # read all files
        subtitle_contents: list[SubtitleFormat] = []
        for subtitle_path in param.subtitle_paths:
            content = parse_subtitle_file(subtitle_path)
            subtitle_contents.append(content)

        if not subtitle_contents:
            logger.warning("No subtitle files found, skipping context preparation.")
            return param
        # pre-translate context
        term_bank = await _prepare_context(
            subtitle_contents,
            param.target_language,
            metadata=param.metadata,
            term_bank=param.term_bank,
        )

        # save pre-translate context
        save_pre_translate_store(param.base_path, term_bank)

    # Print pre-translate context and metadata
    logger.info("Prepared context:")
    for k, context in term_bank.context.items():
        logger.info(f"  {k} -> {context.translated} ({context.description})")

    return param.update(term_bank=term_bank)


async def task_translate_files(param: TaskParameter) -> TaskParameter:
    """
    Translates the subtitle files in the base path.
    """
    subtitle_paths = param.subtitle_paths

    param.set_description("Parsing subtitle files") if param.set_description else None
    subtitle_formats = [parse_subtitle_file(file) for file in subtitle_paths]
    progs = [current_progress().sub_progress() for _ in range(len(subtitle_paths))]

    # translate files
    for subtitle_path, subtitle_format, prog in zip(
        subtitle_paths, subtitle_formats, progs, strict=True
    ):
        param.set_description(
            os.path.basename(subtitle_path)
        ) if param.set_description else None

        output_path = get_output_path(subtitle_path, param.target_language)
        if os.path.exists(output_path):
            logger.info(f"Output file {output_path} already exists, skipping.")
            continue

        try:
            translated_content = await prog.async_monitor(
                translate_file,
                subtitle_format,
                param.target_language,
                param.term_bank,
                metadata=param.metadata,
            )
        except Exception as e:
            logger.error(f"Error translating file {subtitle_path}: {e}, skipping.")
            continue

        translated_content.update_title(f"{param.target_language} (AI Translated)")
        write_translated_subtitle(translated_content.as_str(), output_path)
        logger.info(f"Translated content wrote: {os.path.basename(output_path)}")

    return param


async def task_prepare_metadata(param: TaskParameter) -> TaskParameter:
    """
    Prepares the metadata for the translation.
    """
    param.set_description("Preparing metadata") if param.set_description else None
    metadata = None
    if stored := load_media_set_metadata(param.base_path):
        metadata = stored
    else:
        metadata = await prepare_metadata(param.base_path)
        if metadata:
            save_media_set_metadata(param.base_path, metadata)

    if metadata:
        logger.info(
            f"Anime recognized as: {metadata.title} ({','.join(metadata.title_alt)})"
        )
        logger.debug(f"  {metadata.description}")
        logger.debug("  Characters:")
        for character in metadata.characters:
            logger.debug(
                f"    {character.name}, {character.gender} ({','.join(character.name_alt)})"
            )

    return param.update(metadata=metadata)


def translate(
    path: str,
    target_language: str,
    tasks: tuple[
        Callable[
            [TaskParameter],
            Awaitable[TaskParameter],
        ],
        ...,
    ],
) -> None:
    """
    Translates the subtitles in the given file to the target language.
        :param path: Path to the subtitle files. File can be .srt, .ssa, .ass.
        :param target_language: Target language for translation.
        :param output_path: Path to save the translated subtitles.
    """
    progress_bar = tqdm(
        leave=True,
        position=0,
        colour="#8fbcbb",
        bar_format="{desc} |{bar}| {percentage:3.2f}% [{elapsed}/{remaining}{postfix}]",
    )
    current_progress().set_progress_bar(progress_bar=progress_bar)
    speedometer = Speedometer(progress_bar, unit="chars")

    progs = [current_progress().sub_progress() for _ in range(len(tasks))]

    if os.path.isdir(path) and not path.endswith("/"):
        path = f"{path}/"

    dirname = os.path.basename(os.path.dirname(path))

    task_param = TaskParameter(
        base_path=path,
        target_language=target_language,
        set_description=lambda x: progress_bar.set_description(f"[{dirname}] {x}"),
        metadata=load_media_set_metadata(path),  # preload saved data
        term_bank=load_pre_translate_store(path),  # preload saved data
    )

    for sub in task_param.subtitle_paths:
        logger.debug(f"Found subtitle file: {sub}")

    with speedometer:
        for task, prog in zip(tasks, progs):
            task_param = asyncio.run(
                prog.async_monitor(
                    task,
                    task_param,
                )
            )
            prog.finish()

    current_progress().finish()


default_tasks = (
    task_prepare_metadata,
    task_prepare_context,
    task_translate_files,
)

__all__ = [
    "translate",
    "default_tasks",
    "task_prepare_metadata",
    "task_prepare_context",
    "task_translate_files",
]
