from .format import SubtitleFormat
from .srt_format import SubtitleFormatSRT
from .ssa_format import SubtitleFormatSSA


def parse_subtitle_file(path: str) -> SubtitleFormat:
    """
    Parses the subtitle file and returns the appropriate SubtitleFormat object.
    """
    for subtitle_format in [SubtitleFormatSRT, SubtitleFormatSSA]:
        if subtitle_format.match(path):
            return subtitle_format(path)
    raise ValueError(f"Unsupported subtitle format for file: {path}")
