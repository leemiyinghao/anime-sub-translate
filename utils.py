from typing import List
import os, json

from subtitle_types import PreTranslatedContext, RichSubtitleDialogue
from typing import Iterable


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
                or (
                    not path.endswith(
                        (
                            f"{ignore_postfix}.srt",
                            f"{ignore_postfix}.ssa",
                            f"{ignore_postfix}.ass",
                        )
                    )
                ),
                subtitle_files,
            )
        )
    )


def chunk_dialogues(
    dialogues: Iterable[RichSubtitleDialogue],
    limit: int = 5_000,
) -> list[list[RichSubtitleDialogue]]:
    """
    Chunking dialogues into smaller chunks
    :param dialogues: Iterable of SubtitleDialogue
    :return: Iterable of chunks of SubtitleDialogue
    """

    chunks = [[]]
    current_chunk_size = 0
    
    for dialogue in dialogues:
        dialogue_size = len(dialogue["content"])
        
        # Check if adding this dialogue would exceed the limit
        if current_chunk_size + dialogue_size > limit and current_chunk_size > 0:
            chunks.append([])
            current_chunk_size = 0
            
        chunks[-1].append(dialogue)
        current_chunk_size += dialogue_size

    return chunks


def _find_pre_translate_store(path: str) -> str:
    return os.path.join(os.path.dirname(path), ".translate", "pre_translate_store.json")


def load_pre_translate_store(path: str) -> List[PreTranslatedContext]:
    """
    Loads the pre-translate store from a file.
    :param path: Path of the directory containing the pre-translate store.
    :return: List of dictionaries containing pre-translate context.
    """
    store_path = _find_pre_translate_store(path)
    if not os.path.exists(store_path):
        return []
    try:
        with open(store_path, "r", encoding="utf-8") as file:
            stored = json.load(file)
            return [
                PreTranslatedContext(
                    original=item["original"],
                    translated=item["translated"],
                    description=item["description"],
                )
                for item in stored["context"]
            ]
    except Exception as e:
        print(f"Error loading pre-translate store: {e}")

    return []


def save_pre_translate_store(
    path: str,
    pre_translate_context: List[PreTranslatedContext],
) -> None:
    """
    Saves the pre-translate context to a file.
    :param path: Path of the directory containing the pre-translate store.
    :param pre_translate_context: List of dictionaries containing pre-translate context.
    """
    store_path = _find_pre_translate_store(path)
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    try:
        with open(store_path, "w", encoding="utf-8") as file:
            json.dump(
                {"context": pre_translate_context},
                file,
                ensure_ascii=False,
            )
    except Exception as e:
        print(f"Error saving pre-translate store: {e}")
