import os
import tempfile
import unittest

from parameterized import parameterized
from subtitle_types import SubtitleDialogue

from format.ssa_format import SubtitleFormatSSA


class TestSubtitleFormatSSA(unittest.TestCase):
    def setUp(self):
        # Sample SSA content for testing
        self.sample_ssa = """[Script Info]
Title: Sample SSA File
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Hello, world!
Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,This is a second subtitle.
Dialogue: 0,0:00:11.00,0:00:15.00,Default,,0,0,0,,{{\\pos(400,570)}}Third {\\i}subtitle{\\i} with formatting.
Dialogue: 0,0:00:16.00,0:00:20.00,Default,,0,0,0,,Line with \\Nnewline character.
"""
        # Create temporary SSA and ASS files for testing
        self.temp_ssa_file = tempfile.NamedTemporaryFile(suffix=".ssa", delete=False)
        self.temp_ssa_file.write(self.sample_ssa.encode("utf-8"))
        self.temp_ssa_file.close()

        self.temp_ass_file = tempfile.NamedTemporaryFile(suffix=".ass", delete=False)
        self.temp_ass_file.write(
            self.sample_ssa.encode("utf-8")
        )  # Using same content for ASS
        self.temp_ass_file.close()

        # Initialize the subtitle format with the file
        self.ssa_format = SubtitleFormatSSA(self.temp_ssa_file.name)
        self.ssa_format.raw = self.sample_ssa
        self.ssa_format.init_subtitle()

    def tearDown(self):
        # Clean up the temporary files
        os.unlink(self.temp_ssa_file.name)
        os.unlink(self.temp_ass_file.name)

    def test_match_with_ssa_extension(self):
        """Test that match returns True for .ssa files"""
        self.assertTrue(SubtitleFormatSSA.match("subtitle.ssa"))
        self.assertTrue(SubtitleFormatSSA.match("/path/to/subtitle.ssa"))
        self.assertTrue(SubtitleFormatSSA.match("C:\\path\\to\\subtitle.ssa"))

    def test_match_with_ass_extension(self):
        """Test that match returns True for .ass files"""
        self.assertTrue(SubtitleFormatSSA.match("subtitle.ass"))
        self.assertTrue(SubtitleFormatSSA.match("/path/to/subtitle.ass"))
        self.assertTrue(SubtitleFormatSSA.match("C:\\path\\to\\subtitle.ass"))

    def test_match_with_non_ssa_extension(self):
        """Test that match returns False for non-ssa/ass files"""
        self.assertFalse(SubtitleFormatSSA.match("subtitle.srt"))
        self.assertFalse(SubtitleFormatSSA.match("subtitle.txt"))
        self.assertFalse(SubtitleFormatSSA.match("subtitle"))

    def test_dialogues_extraction(self):
        """Test that dialogues correctly extracts SubtitleDialogue objects from SSA format"""
        expected = [
            SubtitleDialogue(id="0.0", content="Hello, world!", style="Default"),
            SubtitleDialogue(
                id="1.0", content="This is a second subtitle.", style="Default"
            ),
            SubtitleDialogue(
                id="2.1",
                content="Third ",
                style="Default",
            ),
            SubtitleDialogue(
                id="2.3",
                content="subtitle",
                style="Default",
            ),
            SubtitleDialogue(
                id="2.5",
                content=" with formatting.",
                style="Default",
            ),
            SubtitleDialogue(
                id="3.0", content="Line with \\Nnewline character.", style="Default"
            ),
        ]

        dialogues = list(self.ssa_format.dialogues())

        self.assertEqual(dialogues, expected)

    def test_update(self):
        """Test updating subtitle content"""
        expected = [
            SubtitleDialogue(
                id="0.0", content="Modified first subtitle", style="Default"
            ),
            SubtitleDialogue(
                id="1.0", content="Modified second subtitle", style="Default"
            ),
            SubtitleDialogue(id="2.1", content="Modified ", style="Default"),
            SubtitleDialogue(id="2.3", content="SUBTITLE", style="Default"),
            SubtitleDialogue(id="2.5", content=" with formatting.", style="Default"),
            SubtitleDialogue(
                id="3.0", content="Modified fourth \\Nsubtitle", style="Default"
            ),
        ]

        # Get the dialogues
        dialogues = list(self.ssa_format.dialogues())

        # Modify the content
        dialogues[0].content = "Modified first subtitle"
        dialogues[1].content = "Modified second subtitle"
        dialogues[2].content = "Modified "
        dialogues[3].content = "SUBTITLE"
        dialogues[5].content = "Modified fourth \nsubtitle"

        # Update the subtitle
        self.ssa_format.update(iter(dialogues))

        # Get the updated dialogues
        updated_dialogues = list(self.ssa_format.dialogues())

        # Check that the updated dialogues match the expected content
        self.assertEqual(updated_dialogues, expected)

    @parameterized.expand([("0"), ("999"), ("999.0"), ("-1"), ("-1.0"), ("0.-1")])
    def test_update_with_invalid_id(self, invalid_id):
        """Test updating with an invalid subtitle ID"""
        # Create a dialogue with an ID that's out of range
        invalid_dialogue = SubtitleDialogue(id=invalid_id, content="Invalid")

        # Attempt to update with the invalid dialogue
        with self.assertRaises(IndexError):
            self.ssa_format.update([invalid_dialogue])

    def test_update_title(self):
        """Test updating the title of the subtitle"""
        # Update the title
        new_title = "Updated SSA Title"
        self.ssa_format.update_title(new_title)

        # Check that the title was updated
        self.assertEqual(self.ssa_format._raw_format.info["title"], new_title)

        # Check that the title appears in the string representation
        self.assertIn(new_title, self.ssa_format.as_str())

    def test_split_by_formatting(self):
        """Test the _split_by_formatting function with various formatting scenarios."""
        from format.ssa_format import _split_by_formatting

        # Test with no formatting
        plain_text = "Hello world"
        result = _split_by_formatting(plain_text)
        self.assertEqual(result, [("Hello world", False)])

        # Test with single formatting tag
        formatted_text = "Hello {\\i1}world{\\i0}"
        result = _split_by_formatting(formatted_text)
        self.assertEqual(
            result,
            [("Hello ", False), ("{\\i1}", True), ("world", False), ("{\\i0}", True)],
        )

        # Test with multiple formatting tags
        complex_text = "{\\an8}Hello {\\i1}beautiful{\\i0} {\\b1}world{\\b0}"
        result = _split_by_formatting(complex_text)
        self.assertEqual(
            result,
            [
                ("{\\an8}", True),
                ("Hello ", False),
                ("{\\i1}", True),
                ("beautiful", False),
                ("{\\i0}", True),
                (" ", False),
                ("{\\b1}", True),
                ("world", False),
                ("{\\b0}", True),
            ],
        )

        # Test with empty string
        empty_text = ""
        result = _split_by_formatting(empty_text)
        self.assertEqual(result, [])

        # Test with only formatting tags
        only_tags = "{\\i1}{\\b1}{\\u1}"
        result = _split_by_formatting(only_tags)
        self.assertEqual(result, [("{\\i1}", True), ("{\\b1}", True), ("{\\u1}", True)])

        # Test with position tags commonly used in SSA/ASS
        position_text = "{\\pos(400,570)}Positioned text"
        result = _split_by_formatting(position_text)
        self.assertEqual(
            result, [("{\\pos(400,570)}", True), ("Positioned text", False)]
        )

    def test_update_substring(self):
        """Test the _update_substring function with various formatting scenarios."""
        from format.ssa_format import _update_substring

        # Test with no formatting
        plain_text = "Hello world"
        updates = [(0, "Goodbye world")]
        result = _update_substring(plain_text, updates)
        self.assertEqual(result, "Goodbye world")

        # Test with single formatting tag
        formatted_text = "Hello {\\i1}world{\\i0}"
        updates = [(0, "Goodbye "), (2, "everyone")]
        result = _update_substring(formatted_text, updates)
        self.assertEqual(result, "Goodbye {\\i1}everyone{\\i0}")

        # Test with multiple formatting tags
        complex_text = "{\\an8}Hello {\\i1}beautiful{\\i0} {\\b1}world{\\b0}"
        updates = [(1, "Hi "), (3, "wonderful"), (5, " "), (7, "people")]
        result = _update_substring(complex_text, updates)
        self.assertEqual(result, "{\\an8}Hi {\\i1}wonderful{\\i0} {\\b1}people{\\b0}")

        # Test with position tags
        position_text = "{\\pos(400,570)}Positioned text"
        updates = [(1, "Modified text")]
        result = _update_substring(position_text, updates)
        self.assertEqual(result, "{\\pos(400,570)}Modified text")

        # Test with empty updates
        no_updates_text = "Hello {\\i1}world{\\i0}"
        updates = []
        result = _update_substring(no_updates_text, updates)
        self.assertEqual(result, "Hello {\\i1}world{\\i0}")

        # Test with out of range index
        with self.assertRaises(IndexError):
            _update_substring("Hello world", [(5, "test")])


if __name__ == "__main__":
    unittest.main()
