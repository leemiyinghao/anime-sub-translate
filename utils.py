import os
from typing import Iterable, List

from subtitle_types import SubtitleDialogue


def read_subtitle_file(subtitle_file: str) -> str:
    """
    Reads the content of a subtitle file.
    """
    with open(subtitle_file, "r", encoding="utf-8") as file:
        return file.read()


def find_files_from_path(path: str, ignore_postfix: str) -> List[str]:
    ignore_postfix = ignore_postfix.strip(".")
    # Check if path is a directory or a file
    subtitle_files = []
    if os.path.isdir(path):
        # Find all subtitle files in the directory
        for file in os.listdir(path):
            if file.endswith((".srt", ".ssa", ".ass")):
                subtitle_files.append(os.path.join(path, file))
    else:
        # Single file mode
        if path.endswith((".srt", ".ssa", ".ass")):
            subtitle_files = [path]
        else:
            raise ValueError(f"Unsupported file format: {path}")
    return sorted(
        list(
            filter(
                lambda path: (ignore_postfix == "")
                or (not path[:-4].endswith(ignore_postfix)),
                subtitle_files,
            )
        )
    )


def chunk_dialogues(
    dialogues: Iterable[SubtitleDialogue],
    limit: int = 5_000,
) -> list[list[SubtitleDialogue]]:
    """
    Chunking dialogues into smaller chunks
    :param dialogues: Iterable of SubtitleDialogue
    :return: Iterable of chunks of SubtitleDialogue
    """

    chunks = [[]]
    current_chunk_size = 0

    for dialogue in dialogues:
        dialogue_size = len(dialogue.content)

        # Check if adding this dialogue would exceed the limit
        if current_chunk_size + dialogue_size > limit and current_chunk_size > 0:
            chunks.append([])
            current_chunk_size = 0

        chunks[-1].append(dialogue)
        current_chunk_size += dialogue_size

    return chunks


def dialogue_remap_id(
    dialogues: Iterable[SubtitleDialogue],
) -> tuple[list[SubtitleDialogue], dict[str, str]]:
    """
    Remaps the IDs of the dialogues to reduce token length.
    :param dialogues: The list of dialogues to remap.
    :return: A tuple containing the remapped dialogues and a dictionary of old to new ID mappings.
    """
    id_mapping = {}
    remapped_dialogues = []
    for idx, dialogue in enumerate(dialogues):
        new_id = str(idx)
        id_mapping[new_id] = dialogue.id
        remapped_dialogues.append(
            SubtitleDialogue(
                id=new_id,
                **dialogue.model_dump(exclude={"id"}),
            )
        )
    return remapped_dialogues, id_mapping


def dialogue_remap_id_reverse(
    dialogues: Iterable[SubtitleDialogue],
    id_mapping: dict[str, str],
) -> list[SubtitleDialogue]:
    """
    Reverses the ID remapping for the dialogues.
    :param dialogues: The list of dialogues to remap.
    :param id_mapping: The dictionary of old to new ID mappings.
    :return: The remapped dialogues.
    """
    remapped_dialogues = []
    for dialogue in dialogues:
        old_id = id_mapping.get(dialogue.id) or dialogue.id
        remapped_dialogues.append(
            SubtitleDialogue(
                id=old_id,
                **dialogue.model_dump(exclude={"id"}),
            )
        )
    return remapped_dialogues
