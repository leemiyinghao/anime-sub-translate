import os
import tempfile
import unittest

from parameterized import parameterized
from pysubs2 import SSAEvent, SSAFile
from subtitle_types import Dialogue

from format.ssa_format import (
    SectionedEvent,
    SSAFileWrapper,
    SubtitleFormatSSA,
    _backward_dedpulicate,
    _deserialize_id,
    _serialize_id,
    _split_by_formatting,
)


class TestSectionedEvent(unittest.TestCase):
    def setUp(self):
        # Create sample SSAEvents for testing
        self.event_simple = SSAEvent(start=1000, end=5000, text="Hello, world!")
        self.event_formatted = SSAEvent(
            start=6000,
            end=10000,
            text="This is {\\i1}italic{\\i0} text.",
        )
        self.event_complex = SSAEvent(
            start=11000,
            end=15000,
            text="{\\pos(1,2)}Complex {\\b1}bold {\\i1}and italic{\\i0}{\\b0} example.",
        )

        # Initialize SectionedEvent instances
        self.sectioned_simple = SectionedEvent(self.event_simple)
        self.sectioned_formatted = SectionedEvent(self.event_formatted)
        self.sectioned_complex = SectionedEvent(self.event_complex)

    def test_initialization(self):
        """Test SectionedEvent initialization and section splitting."""
        self.assertEqual(self.sectioned_simple._raw, self.event_simple)
        self.assertEqual(self.sectioned_simple._sections, [("Hello, world!", False)])
        self.assertFalse(self.sectioned_simple.dirty)

        self.assertEqual(self.sectioned_formatted._raw, self.event_formatted)
        self.assertEqual(
            self.sectioned_formatted._sections,
            [
                ("This is ", False),
                ("{\\i1}", True),
                ("italic", False),
                ("{\\i0}", True),
                (" text.", False),
            ],
        )
        self.assertFalse(self.sectioned_formatted.dirty)

        self.assertEqual(self.sectioned_complex._raw, self.event_complex)
        self.assertEqual(
            self.sectioned_complex._sections,
            [
                ("{\\pos(1,2)}", True),
                ("Complex ", False),
                ("{\\b1}", True),
                ("bold ", False),
                ("{\\i1}", True),
                ("and italic", False),
                ("{\\i0}", True),
                ("{\\b0}", True),
                (" example.", False),
            ],
        )
        self.assertFalse(self.sectioned_complex.dirty)

    def test_dirty_property(self):
        """Test the dirty property."""
        self.assertFalse(self.sectioned_simple.dirty)
        self.sectioned_simple.set_text(0, "New text")
        self.assertTrue(self.sectioned_simple.dirty)

    def test_set_text(self):
        """Test setting text for a section."""
        self.sectioned_formatted.set_text(2, "ITALIC")
        self.assertEqual(self.sectioned_formatted._sections[2], ("ITALIC", False))
        self.assertTrue(self.sectioned_formatted.dirty)

        # Test setting text for a formatting section (should still work)
        self.sectioned_formatted.set_text(1, "{\\b1}")
        self.assertEqual(
            self.sectioned_formatted._sections[1], ("{\\b1}", False)
        )  # Note: is_formatting becomes False

    def test_set_text_index_out_of_range(self):
        """Test setting text with an invalid index."""
        with self.assertRaises(IndexError):
            self.sectioned_simple.set_text(1, "Error")
        with self.assertRaises(IndexError):
            self.sectioned_simple.set_text(-1, "Error")

    def test_get_text(self):
        """Test getting the combined text."""
        self.assertEqual(
            self.sectioned_formatted.get_text(),
            "This is {\\i1}italic{\\i0} text.",
        )
        self.sectioned_formatted.set_text(2, "ITALIC")
        self.assertEqual(
            self.sectioned_formatted.get_text(),
            "This is {\\i1}ITALIC{\\i0} text.",
        )

    def test_get_text_with_flush(self):
        """Test getting text and flushing the dirty flag."""
        self.sectioned_formatted.set_text(2, "ITALIC")
        self.assertTrue(self.sectioned_formatted.dirty)
        text = self.sectioned_formatted.get_text(flush=True)
        self.assertEqual(text, "This is {\\i1}ITALIC{\\i0} text.")
        self.assertFalse(self.sectioned_formatted.dirty)

    def test_get_sections(self):
        """Test getting the sections with indices."""
        expected_sections = [
            (0, "This is ", False),
            (1, "{\\i1}", True),
            (2, "italic", False),
            (3, "{\\i0}", True),
            (4, " text.", False),
        ]
        self.assertEqual(self.sectioned_formatted.get_sections(), expected_sections)

        # Test after modification
        self.sectioned_formatted.set_text(2, "ITALIC")
        expected_modified_sections = [
            (0, "This is ", False),
            (1, "{\\i1}", True),
            (2, "ITALIC", False),  # Content changed, is_formatting is False now
            (3, "{\\i0}", True),
            (4, " text.", False),
        ]
        self.assertEqual(
            self.sectioned_formatted.get_sections(), expected_modified_sections
        )

    def test_getitem(self):
        """Test accessing sections using index."""
        self.assertEqual(self.sectioned_formatted[0], ("This is ", False))
        self.assertEqual(self.sectioned_formatted[1], ("{\\i1}", True))
        self.assertEqual(self.sectioned_formatted[2], ("italic", False))

    def test_getitem_index_out_of_range(self):
        """Test accessing sections with an invalid index."""
        with self.assertRaises(IndexError):
            _ = self.sectioned_simple[1]
        with self.assertRaises(IndexError):
            _ = self.sectioned_simple[-1]

    def test_len(self):
        """Test the length of the sections."""
        self.assertEqual(len(self.sectioned_simple), 1)
        self.assertEqual(len(self.sectioned_formatted), 5)
        self.assertEqual(len(self.sectioned_complex), 9)

    def test_getattr(self):
        """Test accessing attributes of the underlying SSAEvent."""
        self.assertEqual(self.sectioned_simple.start, 1000)
        self.assertEqual(self.sectioned_simple.end, 5000)
        self.assertEqual(
            self.sectioned_simple.text, "Hello, world!"
        )  # Accesses original text
        self.assertEqual(self.sectioned_formatted.style, "Default")  # Default value

        # Test accessing an attribute that doesn't exist on SSAEvent
        with self.assertRaises(AttributeError):
            _ = self.sectioned_simple.non_existent_attribute


class TestSSAFileWrapper(unittest.TestCase):
    def setUp(self):
        # Create a sample SSAFile for testing
        self.ssa_file = SSAFile()
        self.ssa_file.info["Title"] = "Test Title"
        # Ensure a default style exists and is copied to avoid modifying the global default
        if "Default" not in self.ssa_file.styles:
            self.ssa_file.styles["Default"] = SSAFile.DEFAULT_STYLE.copy()  # type: ignore
        else:
            self.ssa_file.styles["Default"] = self.ssa_file.styles["Default"].copy()

        self.event1 = SSAEvent(start=1000, end=5000, text="First line.")
        self.event2 = SSAEvent(start=6000, end=10000, text="Second {\\i1}line{\\i0}.")
        self.event3 = SSAEvent(
            start=0, end=500, text="Early line."
        )  # To test sorting in get_sections
        self.ssa_file.append(self.event1)
        self.ssa_file.append(self.event2)
        self.ssa_file.append(self.event3)  # Appended last, but starts earliest

        # Initialize SSAFileWrapper
        self.wrapper = SSAFileWrapper(self.ssa_file)

    def test_initialization(self):
        """Test SSAFileWrapper initialization."""
        self.assertIsInstance(self.wrapper._inner, SSAFile)
        self.assertEqual(len(self.wrapper._sections), 3)
        self.assertIsInstance(self.wrapper._sections[0], SectionedEvent)
        self.assertIsInstance(self.wrapper._sections[1], SectionedEvent)
        self.assertIsInstance(self.wrapper._sections[2], SectionedEvent)
        # Check if SectionedEvents were created correctly
        self.assertEqual(self.wrapper._sections[0]._raw, self.event1)
        self.assertEqual(self.wrapper._sections[1]._raw, self.event2)
        self.assertEqual(self.wrapper._sections[2]._raw, self.event3)

    def test_get_sections(self):
        """Test getting sections, ensuring they are sorted by start time."""
        sections = self.wrapper.get_sections()
        self.assertEqual(len(sections), 3)
        # Check the order based on the original event start times
        self.assertEqual(sections[0][0], 2)  # Index of event3 (starts at 0)
        self.assertEqual(sections[0][1]._raw, self.event3)
        self.assertEqual(sections[1][0], 0)  # Index of event1 (starts at 1000)
        self.assertEqual(sections[1][1]._raw, self.event1)
        self.assertEqual(sections[2][0], 1)  # Index of event2 (starts at 6000)
        self.assertEqual(sections[2][1]._raw, self.event2)

    def test_getitem(self):
        """Test accessing sections using index."""
        self.assertIsInstance(self.wrapper[0], SectionedEvent)
        self.assertEqual(self.wrapper[0]._raw, self.event1)
        self.assertEqual(self.wrapper[1]._raw, self.event2)
        self.assertEqual(self.wrapper[2]._raw, self.event3)

    def test_getitem_index_out_of_range(self):
        """Test accessing sections with an invalid index."""
        with self.assertRaisesRegex(IndexError, "Subtitle ID out of range"):
            _ = self.wrapper[3]
        with self.assertRaisesRegex(IndexError, "Subtitle ID out of range"):
            _ = self.wrapper[-1]  # Negative index is invalid here

    def test_len(self):
        """Test the length of the wrapper."""
        self.assertEqual(len(self.wrapper), 3)

    def test_update_section(self):
        """Test updating a text section within an event."""
        # Update the first text part of the second event (index 1, section index 0)
        # Event 2 text: "Second {\\i1}line{\\i0}." -> sections: [("Second ", False), ("{\\i1}", True), ("line", False), ("{\\i0}", True), (".", False)]
        self.wrapper.update_section((1, 0, "Modified second "))
        sectioned_event = self.wrapper[1]
        self.assertTrue(sectioned_event.dirty)
        self.assertEqual(sectioned_event._sections[0], ("Modified second ", False))
        # Check original raw event text is not yet modified
        self.assertEqual(self.wrapper._inner[1].text, "Second {\\i1}line{\\i0}.")

    def test_update_section_invalid_event_index(self):
        """Test updating with an invalid event index."""
        with self.assertRaisesRegex(IndexError, "Subtitle ID out of range"):
            self.wrapper.update_section((3, 0, "Error"))
        with self.assertRaisesRegex(IndexError, "Subtitle ID out of range"):
            self.wrapper.update_section((-1, 0, "Error"))

    def test_update_section_invalid_section_index(self):
        """Test updating with an invalid section index within an event."""
        # Event 0 ("First line.") only has one section (index 0)
        with self.assertRaises(IndexError):  # Raised by SectionedEvent.set_text
            self.wrapper.update_section((0, 1, "Error"))
        with self.assertRaises(IndexError):
            self.wrapper.update_section((0, -1, "Error"))

    def test_flush_no_changes(self):
        """Test flush when no changes have been made."""
        original_texts = [e.text for e in self.wrapper._inner]
        self.wrapper.flush()
        new_texts = [e.text for e in self.wrapper._inner]
        self.assertEqual(original_texts, new_texts)
        for section in self.wrapper._sections:
            self.assertFalse(section.dirty)

    def test_flush_with_changes(self):
        """Test flush after updating sections."""
        # Update event 0, section 0
        self.wrapper.update_section((0, 0, "Modified first line."))
        # Update event 1, section 0 and 2
        # Event 1 text: "Second {\\i1}line{\\i0}." -> sections: [("Second ", False), ("{\\i1}", True), ("line", False), ("{\\i0}", True), (".", False)]
        self.wrapper.update_section((1, 0, "MODIFIED "))
        self.wrapper.update_section((1, 2, "LINE"))  # Update "line" part
        self.wrapper.update_section((1, 4, "!"))  # Update "." part

        self.assertTrue(self.wrapper[0].dirty)
        self.assertTrue(self.wrapper[1].dirty)
        self.assertFalse(self.wrapper[2].dirty)  # Event 2 was not touched

        self.wrapper.flush()

        # Verify underlying SSAFile events are updated
        self.assertEqual(self.wrapper._inner[0].text, "Modified first line.")
        # Expected combined text for event 1: "MODIFIED " + "{\\i1}" + "LINE" + "{\\i0}" + "!"
        self.assertEqual(self.wrapper._inner[1].text, "MODIFIED {\\i1}LINE{\\i0}!")
        self.assertEqual(self.wrapper._inner[2].text, "Early line.")  # Unchanged

        # Verify dirty flags are reset
        self.assertFalse(self.wrapper[0].dirty)
        self.assertFalse(self.wrapper[1].dirty)
        self.assertFalse(self.wrapper[2].dirty)

    def test_to_string(self):
        """Test converting the wrapper to a string, implicitly testing flush."""
        # Update event 0, section 0
        self.wrapper.update_section((0, 0, "Modified first line."))
        self.assertTrue(self.wrapper[0].dirty)

        # Use 'srt' format for simpler output check, though SSA/ASS is the native format
        output_string = self.wrapper.to_string("srt", encoding="utf-8")

        # Check if the output contains the modified text (in SRT format)
        self.assertIn("Modified first line.", output_string)
        # Check if the original second line is still there (wasn't modified)
        # Note: Formatting tags are stripped in SRT conversion by pysubs2
        self.assertIn("Second <i>line</i>.", output_string)
        # Check if the dirty flag was reset by to_string (due to flush)
        self.assertFalse(self.wrapper[0].dirty)

        # Test with native format 'ass'
        output_string_ass = self.wrapper.to_string("ass", encoding="utf-8")
        self.assertIn(
            "Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Modified first line.",
            output_string_ass,
        )
        self.assertIn(
            "Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,Second {\\i1}line{\\i0}.",
            output_string_ass,
        )

    def test_getattr_existing(self):
        """Test accessing existing attributes of the underlying SSAFile."""
        self.assertEqual(self.wrapper.info["Title"], "Test Title")
        self.assertIn("Default", self.wrapper.styles)
        self.assertEqual(len(self.wrapper.events), 3)  # Accessing 'events' property

    def test_getattr_non_existing(self):
        """Test accessing non-existing attributes."""
        with self.assertRaises(AttributeError):
            _ = self.wrapper.non_existent_attribute


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
Dialogue: 0,0:00:11.00,0:00:15.00,Default,,0,0,0,,{{\\pos(400,570)}}{comment}Third {\\i}subtitle{\\i} with formatting.
Dialogue: 0,0:00:16.00,0:00:20.00,Default,,0,0,0,,Line with \\Nnewline character.
Dialogue: 0,0:00:16.00,0:00:20.00,Default,,0,0,0,, 
Dialogue: 0,0:00:16.00,0:00:20.00,Default,,0,0,0,,{\\an7\\c&HFFFFFF&\\p1\\blur2\\fscx65\\fscy65\\pos(336,209)}m 332.78 806.58 b 328.06 806.58 319.95 805.68 318.57 799.64 318.04 797.35 318.41 795.82 318.79 794.95 l 329.7 767.8 324.59 766.06 321.5 771.89 319.98 772.39 b 319.98 772.4 318.73 772.81 318.32 772.96 317.83 773.17 317.29 773.28 316.75 773.28 l 314.99 773.28 313.79 771.97 b 312.47 770.53 312.61 768.99 312.86 766.19 l 312.92 765.52 315.96 758.8 b 314.49 756.35 314.33 755.37 314.26 754.95 313.75 751.86 315.85 748.61 318.86 747.86 319.27 747.75 319.78 747.66 320.3 747.59 l 322.98 740.66 324.17 739.95 b 324.96 739.48 326.52 738.7 328.11 738.7 330.43 738.7 332.29 740.28 332.64 742.53 332.69 742.89 332.81 743.66 332.42 745.89 l 336.86 746.88 b 346.84 717.65 348.3 716.96 349.98 716.18 350.14 716.1 350.33 715.99 350.55 715.87 351.98 715.06 354.38 713.71 357.49 713.71 360 713.71 362.38 714.59 364.56 716.34 367.15 718.41 368.17 720.49 368.35 720.88 l 368.74 721.76 367.26 754.04 384.63 758.61 b 386.25 755.18 389.1 750.77 393.27 749.99 393.96 749.86 394.66 749.8 395.34 749.8 400.48 749.8 403.13 753.38 403.41 753.79 l 404.13 754.82 b 404.13 754.82 404.13 756.56 404.14 756.81 404.44 756.84 404.74 756.88 405.04 756.95 406.54 757.3 407.74 758.19 408.41 759.46 408.83 760.27 409.01 761.19 408.93 762.09 l 409.31 765.93 409.31 766.13 b 409.31 766.7 409.19 767.36 408.9 768.03 l 408.9 776.52 402.67 776.52 401.35 780.48 b 400.9 782.48 398.9 789.66 393.22 790.37 392.85 790.41 392.47 790.44 392.09 790.44 387.03 790.44 383.27 786.32 382.33 784.44 381.51 782.79 381.35 780.65 381.32 780.03 l 381.01 775.56 361.26 773.96 349.01 793.18 348.92 793.3 b 344.14 799.71 340.92 803.44 339.34 804.39 337.18 805.69 334.36 806.39 334.05 806.47 l 333.64 806.56 333.22 806.58 b 333.22 806.58 333.06 806.58 332.78 806.58{\\p0}
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
            Dialogue(id="0.0", content="Hello, world!", style="Default"),
            Dialogue(id="1.0", content="This is a second subtitle.", style="Default"),
            Dialogue(
                id="2.2",
                content="Third ",
                style="Default",
            ),
            Dialogue(
                id="2.4",
                content="subtitle",
                style="Default",
            ),
            Dialogue(
                id="2.6",
                content=" with formatting.",
                style="Default",
            ),
            Dialogue(
                id="3.0", content="Line with \nnewline character.", style="Default"
            ),
        ]

        dialogues = list(self.ssa_format.dialogues())

        self.assertEqual(dialogues, expected)

    def test_update(self):
        """Test updating subtitle content"""
        expected = [
            Dialogue(id="0.0", content="Modified first subtitle", style="Default"),
            Dialogue(id="1.0", content="Modified second subtitle", style="Default"),
            Dialogue(id="2.2", content="Modified ", style="Default"),
            Dialogue(id="2.4", content="SUBTITLE", style="Default"),
            Dialogue(id="2.6", content=" with formatting.", style="Default"),
            Dialogue(id="3.0", content="Modified fourth \nsubtitle", style="Default"),
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
        invalid_dialogue = Dialogue(id=invalid_id, content="Invalid")

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

        # Test with no formatting
        plain_text = "Hello world"
        result = _split_by_formatting(plain_text)
        self.assertEqual(result, [("Hello world", False)])

        # Test with single formatting tag
        formatted_text = "Hello {\\i1}world{\\i0}"
        result = _split_by_formatting(formatted_text)
        self.assertEqual(
            result,
            [
                ("Hello ", False),
                ("{\\i1}", True),
                ("world", False),
                ("{\\i0}", True),
            ],
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
        self.assertEqual(
            result,
            [
                ("{\\i1}", True),
                ("{\\b1}", True),
                ("{\\u1}", True),
            ],
        )

        # Test with position tags commonly used in SSA/ASS
        position_text = "{\\pos(400,570)}Positioned text"
        result = _split_by_formatting(position_text)
        self.assertEqual(
            result,
            [
                ("{\\pos(400,570)}", True),
                ("Positioned text", False),
            ],
        )

    def test_id_roundtrip(self):
        """Test the _serialize_id and _deserialize_id functions."""

        # Test with valid ID
        id_pairs = [(1, 2), (3, 4)]
        serialized = _serialize_id(id_pairs)
        deserialized = _deserialize_id(serialized)
        self.assertEqual(id_pairs, deserialized)

        # Test with empty ID
        empty_id = ""
        with self.assertRaises(IndexError):
            _deserialize_id(empty_id)

        # Test with invalid ID format
        invalid_id = "invalid_format"
        with self.assertRaises(IndexError):
            _deserialize_id(invalid_id)

    def test_backward_deduplicate(self):
        """Test the _backward_dedpulicate function."""

        # Test case 1: No duplicates
        sections1 = [(0, 0, "a"), (1, 0, "b"), (2, 0, "c")]
        result1 = _backward_dedpulicate(sections1)
        self.assertEqual(result1, [([(0, 0)], "a"), ([(1, 0)], "b"), ([(2, 0)], "c")])

        # Test case 2: Duplicates within range
        sections2 = [(0, 0, "a"), (1, 0, "b"), (2, 0, "a")]
        result2 = _backward_dedpulicate(sections2, range=5)
        self.assertEqual(result2, [([(0, 0), (2, 0)], "a"), ([(1, 0)], "b")])

        # Test case 3: Duplicates exceeding max_stack
        sections3 = [(i, 0, "a") for i in range(19)]
        result3 = _backward_dedpulicate(sections3, max_stack=5)
        self.assertEqual(len(result3), 4)
        self.assertEqual([len(r) for r, _ in result3], [5, 5, 5, 4])
        self.assertEqual(result3[0][1], "a")

        # Test case 4: Empty input
        sections4 = []
        result4 = _backward_dedpulicate(sections4)
        self.assertEqual(result4, [])


if __name__ == "__main__":
    unittest.main()
