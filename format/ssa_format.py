import re
from typing import Iterable, Mapping

from pysubs2 import SSAFile
from subtitle_types import SubtitleDialogue

from .format import SubtitleFormat


class SubtitleFormatSSA(SubtitleFormat):
    """
    SubtitleFormatSSA is a class that represents the SSA subtitle format.
    It contains methods to parse and write subtitle files in the SSA format.
    """

    _raw_format: SSAFile
    _dialogues: Mapping[str, SubtitleDialogue]

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

    def dialogues(self) -> Iterable[SubtitleDialogue]:
        """
        Returns a string representation of the dialogue in the SSA format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the SSA format, split by new lines.
        """
        # Sort the subtitles by start time
        sorted_subtitles = filter(
            lambda x: x[1].type == "Dialogue",
            sorted(enumerate(self._raw_format), key=lambda x: x[1].start),
        )
        for idx, subtitle in sorted_subtitles:
            sections = _split_by_formatting(subtitle.text)
            for sidx, (text, is_formatting) in enumerate(sections):
                text = text.replace(r"\\N", "\n")
                if is_formatting or len(text.strip()) == 0:
                    # Skip formatting sections
                    continue
                yield SubtitleDialogue(
                    id=_serialize_id(idx, sidx),
                    content=text,
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
            _id, _sid = (None, None)
            try:
                _id, _sid = _deserialize_id(new_subtitle.id)
            except ValueError as e:
                raise IndexError("Invalid subtitle ID format") from e
            if _id >= len(self._raw_format) or _id < 0:
                raise IndexError("Subtitle ID out of range")
            # Replace new lines with \N in the SSA format
            self._raw_format[_id].text = re.sub(
                r"\n",
                r"\\N",
                _update_substring(
                    self._raw_format[_id].text, [(_sid, new_subtitle.content)]
                ),
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


def _serialize_id(id: int, sid: int) -> str:
    return f"{id}.{sid}"


def _deserialize_id(id: str) -> tuple[int, int]:
    _id, _sid = id.split(".")
    return int(_id), int(_sid)


def _split_by_formatting(content: str) -> list[tuple[str, bool]]:
    """
    Split the SSA subtitle content by any formatting like {\\i}.
    :param content: The SSA subtitle content.
    :return: The split content, containing tuples of (text, is_formatting).
    """

    # Regex can not handle nested formatting, hence we use a simple parser
    stack = []
    breakpoints: list[tuple[int, int]] = []
    for i, c in enumerate(content):
        if c == "{":
            stack.append(i)
        elif c == "}" and (len(stack) > 0):
            if ((existed := stack.pop()) is not None) and len(stack) == 0:
                breakpoints.append((existed, i + 1))
        else:
            pass

    sections = []
    step = 0
    for start, end in breakpoints:
        # Split the content into sections
        sections.append((content[step:start], False))
        sections.append((content[start:end], True))
        step = end
    sections.append((content[step:], False))

    sections = list(filter(lambda x: len(x[0]) > 0, sections))

    return sections


def _update_substring(old: str, new: Iterable[tuple[int, str]]) -> str:
    """
    Replaces the old substring with the new substring in the raw text of the subtitle file.
    :param old: The old substring to be replaced.
    :param new: The new substring to replace the old one.
    :return: The raw text with the substring replaced.
    """
    sections = [c for c, _ in _split_by_formatting(old)]
    for idx, replacement in new:
        if idx >= len(sections) or idx < 0:
            raise IndexError("Index out of range")
        sections[idx] = replacement

    return "".join(sections)
