import re
from collections import OrderedDict
from typing import Iterable, Mapping, Optional

from pysubs2 import SSAEvent, SSAFile
from subtitle_types import Dialogue

from .format import SubtitleFormat

Section = tuple[int, int, str]
IdPair = tuple[int, int]
ComplexSection = tuple[list[IdPair], str]


class SectionedEvent:
    _sections: list[tuple[str, bool]]
    _raw: SSAEvent
    _dirty: bool = False

    def __init__(self, raw: SSAEvent) -> None:
        """
        Initializes the SectionedEvent object with the given SSAEvent.
        :param raw: The SSAEvent object to be initialized.
        """
        self._raw = raw
        self._sections = _split_by_formatting(raw.text)
        self._dirty = False

    @property
    def dirty(self) -> bool:
        """
        Returns True if the sections have been modified.
        :return: True if the sections have been modified, False otherwise.
        """
        return self._dirty

    def set_text(self, idx: int, text: str) -> None:
        """
        Sets the text of the section at the given index.
        :param idx: The index of the section to be set.
        :param text: The text to be set.
        """
        if idx >= len(self._sections) or idx < 0:
            raise IndexError("Index out of range")
        self._sections[idx] = (text, False)
        self._dirty = True

    def get_text(self, flush: bool = False) -> str:
        if flush:
            self._dirty = False
        return "".join([s for s, _ in self._sections])

    def get_sections(self) -> list[tuple[int, str, bool]]:
        """
        Returns the sections of the dialogue.
        :return: The sections of the dialogue.
        """
        return [(idx, s, i) for idx, (s, i) in enumerate(self._sections)]

    def __getitem__(self, idx: int) -> tuple[str, bool]:
        """
        Returns the section at the given index.
        :param idx: The index of the section to be returned.
        :return: The section at the given index.
        """
        if idx >= len(self._sections) or idx < 0:
            raise IndexError("Index out of range")
        return self._sections[idx]

    def __len__(self) -> int:
        """
        Returns the length of the sections.
        :return: The length of the sections.
        """
        return len(self._sections)

    def __getattr__(self, item: str):
        """
        Return attribute of self, or self._raw if not found.
        :param item: The name of the attribute to be returned.
        :return: The value of the attribute.
        """
        if item in self.__dict__:
            return self.__dict__[item]
        return getattr(self._raw, item)


class SSAFileWrapper:
    _inner: SSAFile
    _sections: list[SectionedEvent]

    def __init__(self, raw: SSAFile) -> None:
        self._set_inner(raw)

    def _set_inner(self, raw: SSAFile) -> None:
        """
        Sets the raw text of the subtitle file.
        :param raw: The raw text of the subtitle file.
        """
        self._inner = raw
        self._sections = [SectionedEvent(event) for event in self._inner]

    def get_sections(self) -> list[tuple[int, SectionedEvent]]:
        """
        Returns the sections of the subtitle file.
        """
        _sectioned_events = [
            (idx, _sectioned_event)
            for idx, _sectioned_event in enumerate(self._sections)
        ]
        _sectioned_events.sort(key=lambda x: x[1].start)
        return _sectioned_events

    def __getitem__(self, idx: int) -> SectionedEvent:
        """
        Returns the section at the given index.
        :param idx: The index of the section to be returned.
        :return: The section at the given index.
        """
        if idx >= len(self._sections) or idx < 0:
            raise IndexError("Subtitle ID out of range")
        return self._sections[idx]

    def __len__(self) -> int:
        """
        Returns the length of the sections.
        :return: The length of the sections.
        """
        return len(self._sections)

    def update_section(self, section: Section):
        """
        Updates the section of the subtitle file.
        :param section: The section to be updated.
        """
        idx, sid, text = section
        if idx >= len(self._sections) or idx < 0:
            raise IndexError("Subtitle ID out of range")
        self._sections[idx].set_text(sid, text)

    def flush(self) -> None:
        """
        Flushes the changes made to the sections of the subtitle file.
        """
        for idx, section in enumerate(self._sections):
            if not section.dirty:
                continue
            # Update the text of the section
            self._inner[idx].text = section.get_text(flush=True)

    def to_string(self, format: str, encoding: str) -> str:
        self.flush()
        return self._inner.to_string(format, encoding=encoding)

    def __getattr__(self, item: str):
        """
        Return attribute of self, or self._raw if not found.
        :param item: The name of the attribute to be returned.
        :return: The value of the attribute.
        """
        if item in self.__dict__:
            return self.__dict__[item]
        return getattr(self._inner, item)


class SubtitleFormatSSA(SubtitleFormat):
    """
    SubtitleFormatSSA is a class that represents the SSA subtitle format.
    It contains methods to parse and write subtitle files in the SSA format.
    """

    _raw_format: SSAFileWrapper
    _dialogues: Mapping[str, Dialogue]

    def init_subtitle(self) -> None:
        """
        Initializes the subtitle with the raw text.
        :param raw: The raw text of the subtitle file.
        """
        self._raw_format = SSAFileWrapper(
            SSAFile.from_string(self.raw, encoding="utf-8")
        )

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
        sections = [
            (idx, sid, inner_section_text)
            for idx, outer_section in self._raw_format.get_sections()
            for sid, inner_section_text, is_formatting in outer_section.get_sections()
            if not is_formatting
        ]
        sections = _backward_dedpulicate(sections, range=16)

        for id_pairs, text in sections:
            # Create a new SubtitleDialogue object for each deduplicated section
            yield Dialogue(
                id=_serialize_id(id_pairs),
                content=re.sub(r"\\+N", "\n", text),
                actor=self._raw_format[id_pairs[0][0]].name or None,
                style=self._raw_format[id_pairs[0][0]].style or None,
            )

    def update(self, subtitle_dialogues: Iterable[Dialogue]) -> None:
        """
        Updates the raw text of the subtitle file by replacing the content of the subtitles.
        :param subtitleDialogues: The generator of SubtitleDialogue objects.
        """
        for new_subtitle in subtitle_dialogues:
            for idx, sid in _deserialize_id(new_subtitle.id):
                self._raw_format.update_section(
                    (idx, sid, re.sub("\n", r"\\N", new_subtitle.content))
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

    # Remove empty sections
    sections = [(s, i) for s, i in sections if len(s) > 0]

    sections = sections

    return sections


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
