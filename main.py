import os, argparse, asyncio
from llm import translate, translate_names
from format import parse_subtitle_file
from utils import read_subtitle_file, split_into_chunks, find_files_from_path
import logging
from tqdm.auto import tqdm

logger = logging.getLogger(__name__)

def get_language_postfix(target_language: str) -> str:
    """
    Gets the language postfix from environment variables or defaults to the target language.
    """
    return os.environ.get("LANGUAGE_POSTFIX", target_language)

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
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(translated_content.strip() + '\n')
    except Exception as e:
        print(f"Error writing translated subtitle to {output_path}: {e}")


async def translate_content(subtitle_content: str, target_language: str, pre_translated_entries: str) -> str:
    """
    Translates the subtitle content in chunks.
    """
    # Use split_into_chunks to split the content into manageable chunks
    max_chunk_size = 8_000  # Characters per chunk (adjust based on token limits)
    chunks = split_into_chunks(subtitle_content, max_chunk_size)

    translated_chunks = await asyncio.gather(*[translate(chunk, target_language, pre_translated_entries, idx + 1) for idx, chunk in enumerate(chunks)])

    translated_content = "\n".join([c.strip() for c in translated_chunks])

    return translated_content



def translate_subtitle(path: str, target_language: str) -> None:
    """
     Translates the subtitles in the given file to the target language.
         :param path: Path to the subtitle files. File can be .srt, .ssa, .ass.
         :param target_language: Target language for translation.
         :param output_path: Path to save the translated subtitles.
    """

    try:
        subtitle_files = find_files_from_path(path, get_language_postfix(target_language))
        if not subtitle_files:
            print(f"No subtitle files found in {path}")
            return

        # read all files
        subtitle_contents = []
        for subtitle_file in subtitle_files:
            content = read_subtitle_file(subtitle_file)
            subtitle_contents.append(content)
        
        # Pack pre-translate request
        subtitle_formats = [parse_subtitle_file(file) for file in subtitle_files]
        pre_translate_requests = [format.dialogue(content) for (format, content) in zip(subtitle_formats, subtitle_contents)]
        pre_translated_entries = translate_names('\n'.join(pre_translate_requests), target_language)
        print(f"Pre-translated Entries:\n{pre_translated_entries}\n")

        for subtitle_format, subtitle_file, subtitle_content in tqdm(list(zip(subtitle_formats, subtitle_files, subtitle_contents)), desc=f"Translate files in ...{path[-20:]}", unit="file", position=0):
            output_path = get_output_path(subtitle_file, target_language)
            if os.path.exists(output_path):
                print(f"Output file {output_path} already exists. Skipping translation.")
                continue

            translated_content = asyncio.run(translate_content(subtitle_content, target_language, pre_translated_entries))

            # replace Title line in support format like ASS/SSA
            translated_content = subtitle_format.replace_title(translated_content, f"{target_language} (AI Translated)")

            # try to fix known syntax errors caused by LLMs
            translated_content = subtitle_format.try_fix_syntax_error(translated_content)
        
            write_translated_subtitle(translated_content, output_path)
            print(f"Translated content wrote: {output_path[-20:]}")

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
