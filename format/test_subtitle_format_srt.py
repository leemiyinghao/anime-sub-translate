import unittest
import os
import tempfile
from format import SubtitleFormatSRT

class TestSubtitleFormatSRT(unittest.TestCase):
    def setUp(self):
        self.srt_format = SubtitleFormatSRT()
        
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
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.srt', delete=False)
        self.temp_file.write(self.sample_srt.encode('utf-8'))
        self.temp_file.close()
        
    def tearDown(self):
        # Clean up the temporary file
        os.unlink(self.temp_file.name)
    
    def test_match_with_srt_extension(self):
        """Test that match returns True for .srt files"""
        self.assertTrue(self.srt_format.match('subtitle.srt'))
        self.assertTrue(self.srt_format.match('/path/to/subtitle.srt'))
        self.assertTrue(self.srt_format.match('C:\\path\\to\\subtitle.srt'))
    
    def test_match_with_non_srt_extension(self):
        """Test that match returns False for non-srt files"""
        self.assertFalse(self.srt_format.match('subtitle.txt'))
        self.assertFalse(self.srt_format.match('subtitle.ssa'))
        self.assertFalse(self.srt_format.match('subtitle.ass'))
        self.assertFalse(self.srt_format.match('subtitle'))
    
    def test_dialogue_extraction(self):
        """Test that dialogue correctly extracts text from SRT format"""
        expected_dialogue = "Hello, world! My name is John Doe.\nThis is a second subtitle. With multiple lines.\nThird subtitle with special characters: !@#$%^&*()_+"
        
        with open(self.temp_file.name, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = self.srt_format.dialogue(content)
        self.assertEqual(result, expected_dialogue)
    
    def test_dialogue_with_empty_srt(self):
        """Test dialogue extraction with empty SRT content"""
        result = self.srt_format.dialogue("")
        self.assertEqual(result, "")
    
    def test_dialogue_with_malformed_srt(self):
        """Test dialogue extraction with malformed SRT content"""
        malformed_srt = """This is not a proper SRT file
It has no timestamps or subtitle numbers
Just plain text"""
        
        result = self.srt_format.dialogue(malformed_srt)
        self.assertEqual(result, "")
    
    def test_dialogue_with_complex_formatting(self):
        """Test dialogue extraction with complex formatting in SRT"""
        complex_srt = """1
00:00:01,000 --> 00:00:05,000
<i>Italic text</i>
<b>Bold text</b>

2
00:00:06,000 --> 00:00:10,000
Text with line
breaks and    extra    spaces

"""
        expected = "Italic text Bold text\nText with line breaks and extra spaces"
        result = self.srt_format.dialogue(complex_srt)
        self.assertEqual(result, expected)
    
    def test_dialogue_with_irregular_spacing(self):
        """Test dialogue extraction with irregular spacing in SRT"""
        irregular_srt = """1
00:00:01,000-->00:00:05,000
Text with irregular spacing

2
  00:00:06,000   -->   00:00:10,000  
  More text with irregular spacing  

"""
        expected = "Text with irregular spacing\nMore text with irregular spacing"
        result = self.srt_format.dialogue(irregular_srt)
        self.assertEqual(result, expected)
    
    def test_dialogue_with_multiple_consecutive_subtitles(self):
        """Test dialogue extraction with multiple consecutive subtitles without blank lines"""
        consecutive_srt = """1
00:00:01,000 --> 00:00:05,000
First subtitle
2
00:00:06,000 --> 00:00:10,000
Second subtitle
3
00:00:11,000 --> 00:00:15,000
Third subtitle
"""
        expected = "First subtitle\nSecond subtitle\nThird subtitle"
        result = self.srt_format.dialogue(consecutive_srt)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
