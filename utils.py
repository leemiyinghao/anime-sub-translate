from typing import List
import os

def _handle_long_line(line: str, max_chunk_size: int, chunks: List[str]) -> None:
    """
    Handles lines that are longer than the maximum chunk size by splitting them into smaller pieces.
    """
    remaining_line = line
    while len(remaining_line) > 0:
        # Take a piece that fits in the chunk size
        piece_size = min(max_chunk_size, len(remaining_line))
        chunks.append(remaining_line[:piece_size])
        remaining_line = remaining_line[piece_size:]

def _add_chunk(current_chunk: str, chunks: List[str]) -> str:
    """
    Adds the current chunk to the list of chunks if it's not empty and resets the current chunk.
    """
    if current_chunk:
        chunks.append(current_chunk)
    return ""
    
def _process_line(line: str, max_chunk_size: int, current_chunk: str, chunks: List[str]) -> str:
    """
    Processes a single line, adding it to the current chunk or splitting it into smaller chunks if necessary.
    """
    if len(current_chunk) + len(line) > max_chunk_size:
        current_chunk = _add_chunk(current_chunk, chunks)
    return current_chunk + line


def split_into_chunks(text: str, max_chunk_size: int) -> list:
    """
    Splits the text into chunks of a specified size.
        :param text: The text to split.
        :param max_chunk_size: The maximum size of each chunk.
        :return: A list of text chunks.
    """
    # Split the text into lines
    lines = text.splitlines(True)  # Keep the newline characters
    
    chunks = []
    current_chunk = ""
    
    # Process each line
    for line in lines:
        # If adding this line would exceed the limit, start a new chunk
        if len(line) > max_chunk_size:
            current_chunk = _add_chunk(current_chunk, chunks)
            _handle_long_line(line, max_chunk_size, chunks)
            current_chunk = ""
        else:
            current_chunk = _process_line(line, max_chunk_size, current_chunk, chunks)
    current_chunk = _add_chunk(current_chunk, chunks)
    return [chunk.rstrip('\n') for chunk in chunks]

def read_subtitle_file(subtitle_file: str) -> str:
    """
    Reads the content of a subtitle file.
    """
    with open(subtitle_file, 'r', encoding='utf-8') as file:
        return file.read()

def find_files_from_path(path: str, ignore_postfix: str) -> List[str]:
    ignore_postfix = ignore_postfix.strip('.')
    # Check if path is a directory or a file
    subtitle_files = []
    if os.path.isdir(path):
        # Find all subtitle files in the directory
        for file in os.listdir(path):
            if file.endswith(('.srt', '.ssa', '.ass')):
                subtitle_files.append(os.path.join(path, file))
    else:
        # Single file mode
        if path.endswith(('.srt', '.ssa', '.ass')):
            subtitle_files = [path]
        else:
            raise ValueError(f"Unsupported file format: {path}")
    return sorted(list(filter(lambda path: (ignore_postfix == "") or (not path.endswith((f'{ignore_postfix}.srt', f'{ignore_postfix}.ssa', f'{ignore_postfix}.ass'))), subtitle_files)))
