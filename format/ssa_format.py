import re
from collections import OrderedDict
from typing import Iterable, Mapping, Optional

from logger import logger
from pysubs2 import SSAFile
from subtitle_types import Dialogue

from .format import SubtitleFormat

Section = tuple[int, int, str]
IdPair = tuple[int, int]
ComplexSection = tuple[list[IdPair], str]


class SubtitleFormatSSA(SubtitleFormat):
    """
    SubtitleFormatSSA is a class that represents the SSA subtitle format.
    It contains methods to parse and write subtitle files in the SSA format.
    """

    _raw_format: SSAFile
    _dialogues: Mapping[str, Dialogue]

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

    def dialogues(self) -> Iterable[Dialogue]:
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
        sections: list[Section] = []
        for idx, subtitle in sorted_subtitles:
            # Split the subtitle text by formatting
            sections.extend(
                [
                    (idx, sidx, text)
                    for sidx, (text, is_formatting) in enumerate(
                        _split_by_formatting(subtitle.text)
                    )
                    if not is_formatting
                ]
            )
        # Deduplicate the dialogues
        deduplicated_sections = _backward_dedpulicate(sections, range=16)

        for id_pairs, text in deduplicated_sections:
            # Create a new SubtitleDialogue object for each deduplicated section
            text = re.sub(r"\\+N", "\n", text)
            yield Dialogue(
                id=_serialize_id(id_pairs),
                content=text,
                actor=self._raw_format[id_pairs[0][0]].name or None,
                style=self._raw_format[id_pairs[0][0]].style or None,
            )

    def update(self, subtitle_dialogues: Iterable[Dialogue]) -> None:
        """
        Updates the raw text of the subtitle file by replacing the content of the subtitles.
        :param subtitleDialogues: The generator of SubtitleDialogue objects.
        """
        for new_subtitle in subtitle_dialogues:
            # Update the content of the subtitle
            _id_pairs = _deserialize_id(new_subtitle.id)
            for _id, _sid in _id_pairs:
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


def _serialize_id(id_pairs: Iterable[IdPair]) -> str:
    """
    Serializes the ID pairs into a string format.
    :param id_pairs: The ID pairs to be serialized.
    :return: The serialized ID string.
    """
    return "_".join([f"{_id}.{_sid}" for _id, _sid in id_pairs])


def _deserialize_id(id: str) -> list[IdPair]:
    """
    Deserializes the ID string into a list of ID pairs.
    :param id: The ID string to be deserialized.
    :return: The list of ID pairs.
    """
    result = []
    for pair in id.split("_"):
        try:
            _id, _sid = pair.split(".")
            result.append((int(_id), int(_sid)))
        except ValueError as e:
            raise IndexError(f"Invalid ID format: {pair}") from e

    return result


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
            logger.exception(f"Index out of range: {idx}/{len(sections)}, {sections}")
            raise IndexError("Index out of range")
        sections[idx] = replacement

    return "".join(sections)


def _backward_dedpulicate(
    sections: Iterable[Section], range: int = 16, max_stack: Optional[int] = None
) -> list[ComplexSection]:
    """
    Deduplicates the dialogues by removing any duplicate content within a specified range.
        :param sections: The sections to be deduplicated.
        :param range: The range within which to check for duplicates.
        :param max_stack: The maximum stack size for the deduplication.
        :return: A list of deduplicated sections, each containing a list of tuples ([(id, sid),...], text).
    """
    deduplicated: list[ComplexSection] = []
    recent: OrderedDict[str, list[tuple[int, int]]] = OrderedDict()
    for idx, sid, text in sections:
        if text in recent:
            _recent = recent[text]
            if max_stack and len(_recent) >= max_stack:
                deduplicated.append((_recent, text))
                _recent = []
            _recent.append((idx, sid))
            recent[text] = _recent
        else:
            recent[text] = [(idx, sid)]
        if len(recent) > range:
            # Remove the oldest entry and push it to the deduplicated list
            (k, v) = recent.popitem(last=False)
            deduplicated.append((v, k))

    # Add the remaining entries to the deduplicated list
    for k, v in recent.items():
        deduplicated.append((v, k))

    return deduplicated
