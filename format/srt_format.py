from typing import Iterable, List

import srt

from subtitle_types import RichSubtitleDialogue, SubtitleDialogue

from .format import SubtitleFormat


class SubtitleFormatSRT(SubtitleFormat):
    _raw_format: List[srt.Subtitle]

    def init_subtitle(self) -> None:
        """
        Initializes the subtitle with the raw text.
        :param raw: The raw text of the subtitle file.
        """
        self._raw_format = list(srt.parse(self.raw))

    @classmethod
    def match(cls, filename: str) -> bool:
        """
        Returns True if the filename matches the SRT format.
        :param filename: The name of the subtitle file.
        :return: True if the filename matches the SRT format, False otherwise.
        """
        return filename.lower().endswith(".srt")

    def dialogues(self) -> Iterable[RichSubtitleDialogue]:
        """
        Returns a string representation of the dialogue in the SRT format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the SRT format, split by new lines.
        """
        # Sort the subtitles by start time
        sorted_subtitles = sorted(self._raw_format, key=lambda x: x.start)
        for idx, subtitle in enumerate(sorted_subtitles):
            yield RichSubtitleDialogue(
                id=idx,
                content=subtitle.content,
                character=None,  # SRT does not have character information
                style=None,  # SRT does not have style information
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
            self._raw_format[new_subtitle["id"]].content = new_subtitle["content"]
