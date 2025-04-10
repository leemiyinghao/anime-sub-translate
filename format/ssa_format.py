import re
from typing import Iterable

from pysubs2 import SSAFile

from subtitle_types import RichSubtitleDialogue, SubtitleDialogue

from .format import SubtitleFormat


class SubtitleFormatSSA(SubtitleFormat):
    """
    SubtitleFormatSSA is a class that represents the SSA subtitle format.
    It contains methods to parse and write subtitle files in the SSA format.
    """

    _raw_format: SSAFile

    def init_subtitle(self) -> None:
        """
        Initializes the subtitle with the raw text.
        :param raw: The raw text of the subtitle file.
        """
        self._raw_format = SSAFile.from_string(self.raw, encoding="utf-8")

    @classmethod
    def match(cls, filename: str) -> bool:
        """
        Returns True if the filename matches the SSA format.
        :param filename: The name of the subtitle file.
        :return: True if the filename matches the SSA format, False otherwise.
        """
        return filename[-4:].lower() in (".ssa", ".ass")

    def dialogues(self) -> Iterable[RichSubtitleDialogue]:
        """
        Returns a string representation of the dialogue in the SSA format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the SSA format, split by new lines.
        """
        # Sort the subtitles by start time
        sorted_subtitles = sorted(enumerate(self._raw_format), key=lambda x: x[1].start)
        for idx, subtitle in sorted_subtitles:
            yield RichSubtitleDialogue(
                id=idx,
                content=subtitle.text,
                actor=subtitle.name or None,
                style=subtitle.style or None,
            )

    def update(self, subtitle_dialogues: Iterable[SubtitleDialogue]) -> None:
        """
        Updates the raw text of the subtitle file by replacing the content of the subtitles.
        :param subtitleDialogues: The generator of SubtitleDialogue objects.
        """
        for new_subtitle in subtitle_dialogues:
            # Update the content of the subtitle
            if new_subtitle["id"] >= len(self._raw_format):
                raise IndexError("Subtitle ID out of range")
            # Replace new lines with \N in the SSA format
            self._raw_format[new_subtitle["id"]].text = re.sub(
                r"\n", r"\\N", new_subtitle["content"]
            )

    def update_title(self, title: str) -> None:
        """
        Replaces the title in the raw text of the subtitle file if applicable.
        :param title: The new title to replace the old one.
        """
        self._raw_format.info["title"] = title

    def as_str(self) -> str:
        """
        Returns the raw text of the subtitle file as a string.
        :return: The raw text of the subtitle file.
        """
        return self._raw_format.to_string("ass", encoding="utf-8")
