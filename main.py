import os, re, argparse
from typing import List
from llm import translate, translate_names
from format import parse_subtitle_file

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
        if len(current_chunk) + len(line) > max_chunk_size:
            # If the current line is too long by itself, we need to split it
            if len(line) > max_chunk_size:
                # Add the current chunk to chunks if it's not empty
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Split the long line into smaller pieces
                remaining_line = line
                while len(remaining_line) > 0:
                    # Take a piece that fits in the chunk size
                    piece_size = min(max_chunk_size, len(remaining_line))
                    chunks.append(remaining_line[:piece_size])
                    remaining_line = remaining_line[piece_size:]
                
                # Reset current chunk
                current_chunk = ""
            else:
                # Add the current chunk to chunks and start a new one with this line
                chunks.append(current_chunk)
                current_chunk = line
        else:
            # Add the line to the current chunk
            current_chunk += line
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def find_files_from_path(path: str, ignore_postfix: str) -> List[str]:
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
    return list(filter(lambda path: not path.endswith((f'{ignore_postfix}.srt', f'{ignore_postfix}.ssa', f'{ignore_postfix}.ass')), subtitle_files))

def translate_subtitle(path: str, target_language: str) -> None:
    """
    Translates the subtitles in the given file to the target language.
        :param path: Path to the subtitle files. File can be .srt, .ssa, .ass.
        :param target_language: Target language for translation.
        :param output_path: Path to save the translated subtitles.
    """

    try:
        # Get language postfix from environment or use target_language
        language_postfix = os.environ.get("LANGUAGE_POSTFIX", target_language)
        
        subtitle_files = find_files_from_path(path, language_postfix)
        if not subtitle_files:
            print(f"No subtitle files found in {path}")
            return

        # read all files
        subtitle_contents = []
        for subtitle_file in subtitle_files:
            with open(subtitle_file, 'r') as file:
                content = file.read()
                subtitle_contents.append(content)
        
        # Pack pre-translate request
        subtitle_formats = [parse_subtitle_file(file) for file in subtitle_files]
        pre_translate_requests = [format.dialogue(content) for (format, content) in zip(subtitle_formats, subtitle_contents)]
        pre_translated_entries = translate_names('\n'.join(pre_translate_requests), target_language)
        print(f"Pre-translated Entries:\n{pre_translated_entries}\n")

        for subtitle_format, subtitle_file, subtitle_content in zip(subtitle_formats, subtitle_files, subtitle_contents):

            print(f"Translating content in chunks...")

            # Use split_into_chunks to split the content into manageable chunks
            max_chunk_size = 8_000  # Characters per chunk (adjust based on token limits)
            chunks = split_into_chunks(subtitle_content, max_chunk_size)

            translated_chunks = []
            for i, chunk in enumerate(chunks):
                print(f"Translating chunk {i+1}/{len(chunks)}...")

                # Translate this chunk
                translated_chunk = translate(chunk, target_language, pre_translated_entries)
                translated_chunks.append(translated_chunk)

            translated_content = "\n".join(translated_chunks)

            # replace Title line in support format like ASS/SSA
            translated_content = subtitle_format.replace_title(translated_content, f"{target_language} (AI Translated)")
        
            # Create output filename with language postfix
            base_name, ext = os.path.splitext(subtitle_file)
            output_file = f"{base_name}.{language_postfix}{ext}"
            
            
            output_dir = os.path.dirname(subtitle_file)
            full_output_path = os.path.join(output_dir, output_file)
            
            # Write the translated content
            with open(full_output_path, 'w', encoding='utf-8') as file:
                file.write(translated_content.strip() + '\n')
            
            print(f"Translated {subtitle_file} saved to {full_output_path}")

        print(f"All subtitles translated successfully ({len(subtitle_files)} files)")
    
    except Exception as e:
        print(f"Error translating subtitles: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate subtitles to a target language.")
    parser.add_argument("path", type=str, help="Path to the subtitle files.")
    parser.add_argument("target_language", type=str, help="Target language for translation.")

    args = parser.parse_args()

    # loading extra environment from .env file, we need some environment variables like OPENROUTER_API_KEY for litellm
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Environment variables loaded from .env file")
    except ImportError:
        print("dotenv package not found. Install with: pip install python-dotenv")
    except Exception as e:
        print(f"Error loading .env file: {e}")

    translate_subtitle(args.path, args.target_language)
