# anime-sub-translate-zh-tw

A script to translate anime subtitles from one language to another, primarily targeting Chinese (Traditional).

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

1.  Clone the repository:

```bash
git clone git@github.com:leemiyinghao/anime-sub-translate.git
cd anime-sub-translate
```

2.  Install dependencies using uv:

```bash
uv pip install .
```

## Usage

```bash
python main.py <target_language> <path_to_subtitle_file>
```

-   `<path_to_subtitle_file>`:  Path to the subtitle file or directory containing subtitle files (.srt, .ssa, .ass).
-   `<target_language>`: Target language for translation (e.g., `English`, `繁體中文`).

### Example

```bash
python main.py 繁體中文 subtitles/episode1.srt
```

This will translate the `episode1.srt` subtitle file to Chinese (Traditional) and save the translated subtitle file as `episode1.繁體中文.srt`.

## Configuration

The script uses environment variables for configuration:

-   `LLM_MODEL`: The language model to use for translation (default: `gpt-3.5-turbo`).
-   `LLM_EXTRA_PROMPT`: Extra prompt to pass to the language model.
-   `LANGUAGE_POSTFIX`: The postfix to use for the translated subtitle file (default: target language).
-   `MAX_INPUT_TOKEN`: Max input token limit of the language model.
-   `MAX_OUTPUT_TOKEN`: Max output token limit of the language model.

You can set these environment variables in a `.env` file in the project root directory.  Example:

```
OPENROUTER_API_KEY=!!!!YOUR_API_KEY!!!!
LLM_MODEL=openrouter/google/gemini-2.0-flash-001
MAX_INPUT_TOKEN=500000
MAX_OUTPUT_TOKEN=5000
LANGUAGE_POSTFIX=zh_tw.ai
LLM_EXTRA_PROMPT=使用標準台灣繁體中文，不可使用簡體中文或中國常用語。使用台灣用語或常用翻譯。不可標註拼音。注意口語風格。注意角色情緒及心境。不必要時省略句末句號（。）。日文發音如無法確定漢字，選擇常用翻譯。避免使用嚴重不適當用詞，使用隱晦詞語代替。
```

You may also found the `.env.example` file in the project root directory for reference.

### Recommended Model

Personal recommendation based on my experience:

#### Gemini 2.0 Flash
My go-to model for translation. It's fast and accurate, almost guaranteeing a better translation than Netflix, and not too many formatting issues.

The only downside is that it will fail a lot on "SAFETY" issues, so if you are translate some subtitle that contains a lot of "SAFETY" issues, you may want to try other models.

#### Claude 3.5 Haiku
A little expensive than Gemini 2.0 Flash, having far less context window, and a little slower. But it will be a decent choice if Gemini 2.0 Flash doesn't work.

#### Gemini 2.0 Flash Lite
Not very recommended due to its significantly lower quality than Gemini 2.0 Flash. But it is a good choice if you are pretty sure that your subtitle are pretty simple and you want to save some money.

#### Gemini 1.5 8B
Quality is significantly too low.

#### GPT Series
Unless you have some discounts or something, I don't recommend using GPT series models for translation. They are just slow and expensive.

However, based on OpenRouter statistics, 4o-mini are quite popular among translation task.

#### Llama 4
Unless you are running a local cluster, but I stongly doubt that it will be better than some popular local models like Mistral.

## Dependencies

-   [litellm](https://github.com/BerriAI/litellm):  Used for interacting with various language models.

## Supported Subtitle Formats

-   SRT (.srt)
-   SSA (.ssa)
-   ASS (.ass)

## Development

### Test

```bash
uv run -m coverage run -m unittest discover
```

### Read Coverage Report

```bash
uv run -m coverage report
```
