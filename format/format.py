from typing import Iterable, TypeAlias

from subtitle_types import Dialogue

RawSubtitle: TypeAlias = str


class SubtitleFormat:
    """
    SubtitleFormat is a class that represents the format of a subtitle file.
    It contains methods to parse and write subtitle files in different formats.
    """

    raw: RawSubtitle

    def __init__(self, filename: str):
        """
        Initializes the SubtitleFormat object with the filename.
        :param filename: The name of the subtitle file.
        """
        # load the subtitle file
        with open(filename, "r", encoding="utf-8") as f:
            self.raw = f.read()
        self.init_subtitle()

    def init_subtitle(self) -> None:
        """
        Initializes the subtitle with the raw text.
        :param raw: The raw text of the subtitle file.
        """
        raise NotImplementedError("Subclasses should implement this!")

    @classmethod
    def match(cls, filename: str) -> bool:
        """
        Returns True if the filename matches the format of the subtitle file.
        :param filename: The name of the subtitle file.
        :param raw: The name of the subtitle file.
        :return: True if the filename matches the format, False otherwise.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def dialogues(self) -> Iterable[Dialogue]:
        """
        Returns a string representation of the dialogue in the subtitle format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the subtitle file, split by new lines.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def update_title(self, title: str) -> None:
        """
        Replaces the title in the raw text of the subtitle file if applicable.
        :param raw: The raw text of the subtitle file.
        :param title: The new title to replace the old one.
        :return: The raw text with the title replaced.
        """
        pass

    def update(self, subtitle_dialogues: Iterable[Dialogue]) -> None:
        """
        Updates the raw text of the subtitle file.
        :param raw: The new raw text of the subtitle file.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def as_str(self) -> str:
        """
        Returns a string representation of the subtitle file.
        :return: The raw text of the subtitle file.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def write(self, filename: str) -> None:
        """
        Writes the raw text of the subtitle file to a new file.
        :param filename: The name of the new subtitle file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.as_str())
