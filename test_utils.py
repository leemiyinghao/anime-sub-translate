import unittest
import os
import tempfile
from utils import split_into_chunks, read_subtitle_file, find_files_from_path

class TestUtils(unittest.TestCase):

    def test_split_into_chunks(self):
        # Test case 1: Basic test with a string containing newlines
        text = "This is a test string.\nThis is another line."
        chunks = split_into_chunks(text, 30)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], "This is a test string.")
        self.assertEqual(chunks[1], "This is another line.")

        # Test case 2: String longer than max_chunk_size
        text = "A" * 50  
        chunks = split_into_chunks(text, 20)        
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], "A" * 20)

    def test_read_subtitle_file(self):
        # Create a dummy subtitle file for testing
        test_file_path = "test_subtitle.srt"
        test_content = "1\n00:00:00,000 --> 00:00:05,000\nHello, world!\n"
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)

        content = read_subtitle_file(test_file_path)
        self.assertEqual(content, test_content)

        # Clean up the dummy file
        os.remove(test_file_path)

    def test_find_files_from_path(self):
        # Create dummy files and directories for testing
        with tempfile.TemporaryDirectory() as test_dir:

            # Create dummy files
            srt_file_path = os.path.join(test_dir, "test_subtitle.srt")
            

            ssa_file_path = os.path.join(test_dir, "test_subtitle.ssa")
            txt_file_path = os.path.join(test_dir, "not_subtitle.txt")

            open(srt_file_path, 'w').close()        
            open(ssa_file_path, 'w').close()        
            open(txt_file_path, 'w').close()

            # Test find_files_from_path
            files = find_files_from_path(test_dir, "")
            self.assertEqual(len(files), 2)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(ssa_file_path in files)

            # Test with ignore_postfix
            files = find_files_from_path(test_dir, "test")
            self.assertEqual(len(files), 2)
