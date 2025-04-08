import unittest
import os
import tempfile
from format import SubtitleFormatSSA

class TestSubtitleFormatSSA(unittest.TestCase):
    def setUp(self):
        self.ssa_format = SubtitleFormatSSA()
        
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
        self.temp_ssa_file.write(self.sample_ssa.encode('utf-8'))
        self.temp_ssa_file.close()
        
        self.temp_ass_file = tempfile.NamedTemporaryFile(suffix='.ass', delete=False)
        self.temp_ass_file.write(self.sample_ssa.encode('utf-8'))  # Using same content for ASS
        self.temp_ass_file.close()
        
    def tearDown(self):
        # Clean up the temporary files
        os.unlink(self.temp_ssa_file.name)
        os.unlink(self.temp_ass_file.name)
    
    def test_match_with_ssa_extension(self):
        """Test that match returns True for .ssa files"""
        self.assertTrue(self.ssa_format.match('subtitle.ssa'))
        self.assertTrue(self.ssa_format.match('/path/to/subtitle.ssa'))
        self.assertTrue(self.ssa_format.match('C:\\path\\to\\subtitle.ssa'))
    
    def test_match_with_ass_extension(self):
        """Test that match returns True for .ass files"""
        self.assertTrue(self.ssa_format.match('subtitle.ass'))
        self.assertTrue(self.ssa_format.match('/path/to/subtitle.ass'))
        self.assertTrue(self.ssa_format.match('C:\\path\\to\\subtitle.ass'))
    
    def test_match_with_non_ssa_extension(self):
        """Test that match returns False for non-ssa/ass files"""
        self.assertFalse(self.ssa_format.match('subtitle.srt'))
        self.assertFalse(self.ssa_format.match('subtitle.txt'))
        self.assertFalse(self.ssa_format.match('subtitle'))
    
    def test_dialogue_extraction(self):
        """Test that dialogue correctly extracts text from SSA format"""
        expected_dialogue = "Hello, world!\nThis is a second subtitle.\nThird subtitle with formatting.\nLine with newline character."
        
        with open(self.temp_ssa_file.name, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = self.ssa_format.dialogue(content)
        self.assertEqual(result, expected_dialogue)
    
    def test_dialogue_with_empty_ssa(self):
        """Test dialogue extraction with empty SSA content"""
        result = self.ssa_format.dialogue("")
        self.assertEqual(result, "")
    
    def test_dialogue_with_malformed_ssa(self):
        """Test dialogue extraction with malformed SSA content"""
        malformed_ssa = """This is not a proper SSA file
It has no sections or formatting
Just plain text"""
        
        result = self.ssa_format.dialogue(malformed_ssa)
        self.assertEqual(result, "")
    
    def test_dialogue_with_missing_format_line(self):
        """Test dialogue extraction with missing Format line"""
        missing_format = """[Script Info]
Title: Sample SSA File

[Events]
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Hello, world!
"""
        result = self.ssa_format.dialogue(missing_format)
        self.assertEqual(result, "")
    
    def test_dialogue_with_complex_formatting(self):
        """Test dialogue extraction with complex formatting in SSA"""
        complex_ssa = """[Script Info]
Title: Complex SSA

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,{{c&H00FF00&}}Colored text
Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,{{b1}}Bold{{b0}} and {{i1}}italic{{i0}}
Dialogue: 0,0:00:11.00,0:00:15.00,Default,,0,0,0,,{{pos(400,570)}\\c&H0000FF&\\b1}}Multiple formatting
"""
        expected = "Colored text\nBold and italic\nMultiple formatting"
        result = self.ssa_format.dialogue(complex_ssa)
        self.assertEqual(result, expected)
    
    def test_dialogue_with_commas_in_text(self):
        """Test dialogue extraction with commas in the text field"""
        commas_ssa = """[Script Info]
Title: SSA with commas

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,Hello, world, with commas!
Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,More, text, with, many, commas
"""
        expected = "Hello, world, with commas!\nMore, text, with, many, commas"
        result = self.ssa_format.dialogue(commas_ssa)
        self.assertEqual(result, expected)
    
    def test_dialogue_with_quoted_text(self):
        """Test dialogue extraction with quoted text in the Text field"""
        quoted_ssa = """[Script Info]
Title: SSA with quotes

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,He said "Hello, world!"
Dialogue: 0,0:00:06.00,0:00:10.00,Default,,0,0,0,,"This entire line is quoted"
"""
        expected = 'He said "Hello, world!"\n"This entire line is quoted"'
        result = self.ssa_format.dialogue(quoted_ssa)
        self.assertEqual(result, expected)
    
    def test_dialogue_with_different_text_column_position(self):
        """Test dialogue extraction when Text column is not the last column"""
        different_format_ssa = """[Script Info]
Title: Different format

[Events]
Format: Layer, Start, End, Text, Style, Name, MarginL, MarginR, MarginV, Effect
Dialogue: 0,0:00:01.00,0:00:05.00,This text is in a different position,Default,,0,0,0,
Dialogue: 0,0:00:06.00,0:00:10.00,Another line in a different position,Default,,0,0,0,
"""
        expected = "This text is in a different position\nAnother line in a different position"
        result = self.ssa_format.dialogue(different_format_ssa)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
