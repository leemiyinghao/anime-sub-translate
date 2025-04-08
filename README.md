# anime-sub-translate-zh-tw

A script to translate anime subtitles from one language to another, primarily targeting Chinese (Traditional).

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

1.  Clone the repository:

```bash
git clone <repository_url>
cd anime-sub-translate
```

2.  Install dependencies using uv:

```bash
uv pip install .
```

## Usage

```bash
python main.py <path_to_subtitle_file> <target_language>
```

-   `<path_to_subtitle_file>`:  Path to the subtitle file or directory containing subtitle files (.srt, .ssa, .ass).
-   `<target_language>`: Target language for translation (e.g., `English`, `繁體中文`).

### Example

```bash
python main.py subtitles/episode1.srt 繁體中文
```

This will translate the `episode1.srt` subtitle file to Chinese (Traditional) and save the translated subtitle file as `episode1.繁體中文.srt`.

## Configuration

The script uses environment variables for configuration:

-   `LLM_MODEL`: The language model to use for translation (default: `gpt-3.5-turbo`).
-   `LLM_EXTRA_PROMPT`: Extra prompt to pass to the language model.
-   `LANGUAGE_POSTFIX`: The postfix to use for the translated subtitle file (default: target language).

You can set these environment variables in a `.env` file in the project root directory.  Example:

```
LLM_MODEL=openrouter/google/gemini-2.0-flash-001
LANGUAGE_POSTFIX=zh_tw.ai
LLM_EXTRA_PROMPT=使用標準台灣繁體中文，不可使用簡體中文或中國常用語。不需要漢語拼音。對白部分注意口語風格，避免太像學術文章。注意角色使用對白時的情緒及心境。不必要時省略句末句號（。）。
```

## Dependencies

-   [litellm](https://github.com/BerriAI/litellm):  Used for interacting with various language models.

## Supported Subtitle Formats

-   SRT (.srt)
-   SSA (.ssa)
-   ASS (.ass)
