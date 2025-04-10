import os
import tempfile
import unittest

from format.srt_format import SubtitleFormatSRT


class TestSubtitleFormatSRT(unittest.TestCase):
    def setUp(self):
        # Sample SRT content for testing
        self.sample_srt = """1
00:00:01,000 --> 00:00:05,000
Hello, world!
My name is John Doe.

2
00:00:06,000 --> 00:00:10,000
This is a second subtitle.
With multiple lines.

3
00:00:11,000 --> 00:00:15,000
Third subtitle with special characters:
!@#$%^&*()_+

"""
        # Create a temporary SRT file for testing
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
        self.temp_file.write(self.sample_srt.encode("utf-8"))
        self.temp_file.close()
        
        # Initialize the subtitle format with the file
        self.srt_format = SubtitleFormatSRT(self.temp_file.name)
        self.srt_format.raw = self.sample_srt
        self.srt_format.init_subtitle()

    def tearDown(self):
        # Clean up the temporary file
        os.unlink(self.temp_file.name)

    def test_match_with_srt_extension(self):
        """Test that match returns True for .srt files"""
        self.assertTrue(SubtitleFormatSRT.match("subtitle.srt"))
        self.assertTrue(SubtitleFormatSRT.match("/path/to/subtitle.srt"))
        self.assertTrue(SubtitleFormatSRT.match("C:\\path\\to\\subtitle.srt"))

    def test_match_with_non_srt_extension(self):
        """Test that match returns False for non-srt files"""
        self.assertFalse(SubtitleFormatSRT.match("subtitle.txt"))
        self.assertFalse(SubtitleFormatSRT.match("subtitle.ssa"))
        self.assertFalse(SubtitleFormatSRT.match("subtitle.ass"))
        self.assertFalse(SubtitleFormatSRT.match("subtitle"))

    def test_dialogues_extraction(self):
        """Test that dialogues correctly extracts SubtitleDialogue objects from SRT format"""
        dialogues = list(self.srt_format.dialogues())
        
        # Check we have the right number of dialogues
        self.assertEqual(len(dialogues), 3)
        
        # Check the content of each dialogue
        self.assertEqual(dialogues[0]["content"], "Hello, world!\nMy name is John Doe.")
        self.assertEqual(dialogues[1]["content"], "This is a second subtitle.\nWith multiple lines.")
        self.assertEqual(dialogues[2]["content"], "Third subtitle with special characters:\n!@#$%^&*()_+")
        
        # Check that character and style are None (SRT doesn't have these)
        for dialogue in dialogues:
            self.assertIsNone(dialogue["character"])
            self.assertIsNone(dialogue["style"])

    def test_update(self):
        """Test updating subtitle content"""
        # Get the dialogues
        dialogues = list(self.srt_format.dialogues())
        
        # Modify the content
        dialogues[0]["content"] = "Modified first subtitle"
        dialogues[1]["content"] = "Modified second subtitle"
        dialogues[2]["content"] = "Modified third subtitle"
        
        # Update the subtitle
        self.srt_format.update(iter(dialogues))
        
        # Get the updated dialogues
        updated_dialogues = list(self.srt_format.dialogues())
        
        # Check the content was updated
        self.assertEqual(updated_dialogues[0]["content"], "Modified first subtitle")
        self.assertEqual(updated_dialogues[1]["content"], "Modified second subtitle")
        self.assertEqual(updated_dialogues[2]["content"], "Modified third subtitle")

    def test_update_with_invalid_id(self):
        """Test updating with an invalid subtitle ID"""
        # Create a dialogue with an ID that's out of range
        invalid_dialogue = {"id": 999, "content": "Invalid", "character": None, "style": None}
        
        # Attempt to update with the invalid dialogue
        with self.assertRaises(IndexError):
            self.srt_format.update([invalid_dialogue])


if __name__ == "__main__":
    unittest.main()
