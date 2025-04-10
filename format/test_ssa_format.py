import os
import tempfile
import unittest

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
Dialogue: 0,0:00:11.00,0:00:15.00,Default,,0,0,0,,{{pos(400,570)}}Third subtitle with formatting.
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
        dialogues = list(self.ssa_format.dialogues())

        # Check we have the right number of dialogues
        self.assertEqual(len(dialogues), 4)

        # Check the content of each dialogue
        self.assertEqual(dialogues[0]["content"], "Hello, world!")
        self.assertEqual(dialogues[1]["content"], "This is a second subtitle.")
        self.assertEqual(
            dialogues[2]["content"], "{{pos(400,570)}}Third subtitle with formatting."
        )
        self.assertEqual(dialogues[3]["content"], "Line with \\Nnewline character.")

        # Check that character is None (not set in our sample)
        for dialogue in dialogues:
            self.assertIsNone(dialogue["actor"])
            self.assertEqual(dialogue["style"], "Default")

    def test_update(self):
        """Test updating subtitle content"""
        # Get the dialogues
        dialogues = list(self.ssa_format.dialogues())

        # Modify the content
        dialogues[0]["content"] = "Modified first subtitle"
        dialogues[1]["content"] = "Modified second subtitle"
        dialogues[2]["content"] = "Modified third subtitle"
        dialogues[3]["content"] = "Modified fourth \nsubtitle"

        # Update the subtitle
        self.ssa_format.update(iter(dialogues))

        # Get the updated dialogues
        updated_dialogues = list(self.ssa_format.dialogues())

        # Check the content was updated
        self.assertEqual(updated_dialogues[0]["content"], "Modified first subtitle")
        self.assertEqual(updated_dialogues[1]["content"], "Modified second subtitle")
        self.assertEqual(updated_dialogues[2]["content"], "Modified third subtitle")
        self.assertEqual(updated_dialogues[3]["content"], r"Modified fourth \Nsubtitle")

    def test_update_with_invalid_id(self):
        """Test updating with an invalid subtitle ID"""
        # Create a dialogue with an ID that's out of range
        invalid_dialogue = {
            "id": 999,
            "content": "Invalid",
            "character": None,
            "style": None,
        }

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


if __name__ == "__main__":
    unittest.main()
