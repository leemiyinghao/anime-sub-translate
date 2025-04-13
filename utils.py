import os
from typing import Callable, Iterable, List, Optional, Sequence, TypeVar

from subtitle_types import SubtitleDialogue


def read_subtitle_file(subtitle_file: str) -> str:
    """
    Reads the content of a subtitle file.
    """
    with open(subtitle_file, "r", encoding="utf-8") as file:
        return file.read()


def find_files_from_path(
    path: str, ignore_postfix: str, match_postfix: Optional[str] = None
) -> List[str]:
    ignore_postfix = ignore_postfix.strip(".")
    # Check if path is a directory or a file
    subtitle_files = []
    if os.path.isdir(path):
        # Find all subtitle files in the directory recursively
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith((".srt", ".ssa", ".ass")):
                    subtitle_files.append(os.path.join(root, file))
    else:
        # Single file mode
        if path.endswith((".srt", ".ssa", ".ass")):
            subtitle_files = [path]
        else:
            raise ValueError(f"Unsupported file format: {path}")

    if ignore_postfix:
        subtitle_files = [
            file for file in subtitle_files if not file[:-4].endswith(ignore_postfix)
        ]
    if match_postfix:
        subtitle_files = [
            file for file in subtitle_files if file[:-4].endswith(match_postfix)
        ]
    return sorted(subtitle_files)


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


def string_similarity(s1: str, s2: str) -> float:
    """
    Calculate the similarity between two strings in terms of character overlap based on Levenshtein Distance, insensitive to case.
    :param s1: The first string.
    :param s2: The second string.
    :return: A float representing the similarity between the two strings.
    """
    s1 = s1.lower()
    s2 = s2.lower()
    if not s1 or not s2:
        return 0.0

    if s1 == s2:
        return 1.0

    # Calculate the Levenshtein distance
    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 0.0
    return 1.0 - distance / max_len


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.
    :param s1: The first string.
    :param s2: The second string.
    :return: The Levenshtein distance between the two strings.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


T = TypeVar("T")


def best_match(
    match: str,
    candidates: Sequence[T],
    key=Callable[[], Iterable[str]],
    threshold: float = 0.5,
) -> Optional[T]:
    """
    Find the best match for a given string from a list of candidates, with threshold.
    :param match: The string to match.
    :param candidates: The list of candidates to match against.
    :param key: A function to extract the string from the candidate.
    :return: The best matching candidate.
    """
    best_candidate = None
    best_similarity = 0.0

    for candidate in candidates:
        candidate_strs = key(candidate)
        if not candidate_strs:
            continue
        if isinstance(candidate_strs, str):
            candidate_strs = [candidate_strs]
        for candidate_str in candidate_strs:
            if not candidate_str:
                continue
            # Calculate the similarity between the match and the candidate string
            similarity = string_similarity(match, candidate_str)
            if similarity > best_similarity:
                best_similarity = similarity
                best_candidate = candidate

    if best_similarity < threshold:
        return None

    return best_candidate
