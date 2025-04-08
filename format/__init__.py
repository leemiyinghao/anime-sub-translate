import re
class SubtitleFormat:
    """
    SubtitleFormat is a class that represents the format of a subtitle file.
    It contains methods to parse and write subtitle files in different formats.
    """
    def match(self, filename: str) -> bool:
        """
        Returns True if the filename matches the format of the subtitle file.
        :param filename: The name of the subtitle file.
        :param raw: The name of the subtitle file.
        :return: True if the filename matches the format, False otherwise.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def dialogue(self, raw: str) -> str:
        """
        Returns a string representation of the dialogue in the subtitle format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the subtitle file, split by new lines.
        """
        raise NotImplementedError("Subclasses should implement this!")

    def replace_title(self, raw: str, title: str) -> str:
        """
        Replaces the title in the raw text of the subtitle file.
        :param raw: The raw text of the subtitle file.
        :param title: The new title to replace the old one.
        :return: The raw text with the title replaced.
        """
        return raw

class SubtitleFormatSRT(SubtitleFormat):
    def match(self, filename: str) -> bool:
        """
        Returns True if the filename matches the SRT format.
        :param filename: The name of the subtitle file.
        :return: True if the filename matches the SRT format, False otherwise.
        """
        return filename.endswith('.srt')
    def dialogue(self, raw: str) -> str:
        """
        Returns a string representation of the dialogue in the SRT format.
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the SRT file.
        """
        
        # Extract dialogue from SRT format
        # Pattern matches subtitle blocks: number, timestamp, and text
        pattern = r'\d+\s*\n\s*(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\s*\d+\s*\n|$)'
        
        matches = re.findall(pattern, raw)
        
        # Extract only the dialogue text (not timestamps)
        dialogue_lines = []
        for _, text in matches:
            # We need to remove any formatting tags.
            cleaned_text = re.sub(r'<[^>]+>', '', text.strip())
            # Clean up the text (remove extra whitespace)
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text.strip())
            
            if cleaned_text:
                dialogue_lines.append(cleaned_text.strip())
        
        return '\n'.join(dialogue_lines)

class SubtitleFormatSSA(SubtitleFormat):
    def match(self, filename: str) -> bool:
        """
        Returns True if the filename matches the SSA format.
        :param filename: The name of the subtitle file.
        :return: True if the filename matches the SSA format, False otherwise.
        """
        return filename.endswith('.ssa') or filename.endswith('.ass')

    def dialogue(self, raw: str) -> str:
        """
        Return a string representation of the dialogue in the SSA format
        :param raw: The raw text of the subtitle file.
        :return: A string representation of the dialogue in the SSA file.
        """
        # Find the Events section
        events_section = re.search(r'\[Events\](.*?)(?=\[[^\]]+\]|$)', raw, re.DOTALL)
        if not events_section:
            return ""

        events_content = events_section.group(1)

        # Find the Format line to determine column positions
        format_line = re.search(r'Format:(.*?)$', events_content, re.MULTILINE)
        if not format_line:
            return ""

        # Parse the format columns
        format_columns = [col.strip().lower() for col in format_line.group(1).split(',')]

        # Find the index of the Text column
        text_index = -1
        for i, col in enumerate(format_columns):
            if col.lower() == 'text':
                text_index = i
                break

        if text_index == -1:
            return ""

        # Extract all dialogue lines
        dialogue_lines = re.findall(r'Dialogue:(.*?)$', events_content, re.MULTILINE)

        # Extract the text from each dialogue line
        texts = []
        for line in dialogue_lines:
            # Split the line by comma, respecting the number of columns
            parts = line.split(',', len(format_columns) - 1)
            
            # Ensure we have enough parts to extract the text field
            if not (len(parts) > text_index):
                continue

            # Get text content (the content at text_index position)
            text = parts[text_index].strip()
            
            # Remove formatting tags like {{pos(400,570)}} or {\pos(400,570)}
            text = re.sub(r'(\{\{.*?\}\}|\{.*?\})', '', text)
            
            # More carefully handle SSA format codes with backslashes
            text = re.sub(r'\\[Nhn]', ' ', text)  # Handle only newline codes
            text = re.sub(r'\\[a-zA-Z0-9&][a-zA-Z0-9&]*', '', text)  # Handle other codes
            
            # Clean up extra whitespace resulting from replacements
            text = re.sub(r'\s+', ' ', text).strip()
            
            if text:
                texts.append(text)

        return '\n'.join(texts)
    
    def replace_title(self, raw: str, title: str) -> str:
        """
        Replaces the title in the raw text of the SSA subtitle file.
        :param raw: The raw text of the subtitle file.
        :param title: The new title to replace the old one.
        :return: The raw text with the title replaced.
        """
        # Replace the title in the Script Info section
        return re.sub(r'(Title:\s*).*', r'\1' + title, raw)

def parse_subtitle_file(path: str) -> SubtitleFormat:
    """
    Parses the subtitle file and returns the appropriate SubtitleFormat object.
    """
    for subtitle_format in [SubtitleFormatSRT(), SubtitleFormatSSA()]:
        if subtitle_format.match(path):
            return subtitle_format
    raise ValueError(f"Unsupported subtitle format for file: {path}")
