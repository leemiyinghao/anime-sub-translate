import unittest
import os
import tempfile
from utils import (
    read_subtitle_file,
    find_files_from_path,
    chunk_dialogues,
    save_pre_translate_store,
    load_pre_translate_store,
)
from subtitle_types import RichSubtitleDialogue, PreTranslatedContext


class TestUtils(unittest.TestCase):
    def test_read_subtitle_file(self):
        # Create a dummy subtitle file for testing
        test_file_path = "test_subtitle.srt"
        test_content = "1\n00:00:00,000 --> 00:00:05,000\nHello, world!\n"
        with open(test_file_path, "w", encoding="utf-8") as f:
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
            ssa_file_path = os.path.join(test_dir, "test_subtitle.translated.ssa")
            ass_file_path = os.path.join(test_dir, "test_subtitle.ass")
            txt_file_path = os.path.join(test_dir, "not_subtitle.txt")

            open(srt_file_path, "w").close()
            open(ssa_file_path, "w").close()
            open(ass_file_path, "w").close()
            open(txt_file_path, "w").close()

            # Test find_files_from_path
            files = find_files_from_path(test_dir, "")
            self.assertEqual(len(files), 3)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(ssa_file_path in files)
            self.assertTrue(ass_file_path in files)

            # Test with ignore_postfix
            files = find_files_from_path(test_dir, "translated")
            self.assertEqual(len(files), 2)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(ass_file_path in files)

    def test_chunk_dialogues(self):
        # Create sample dialogues
        dialogues = [
            RichSubtitleDialogue(
                id=1, content="A" * 2000, actor="John", style="Default"
            ),
            RichSubtitleDialogue(
                id=2, content="B" * 2000, actor="Jane", style="Default"
            ),
            RichSubtitleDialogue(
                id=3, content="C" * 2000, actor="John", style="Default"
            ),
            RichSubtitleDialogue(
                id=4, content="D" * 2000, actor="Jane", style="Default"
            ),
        ]

        # Test chunking with default limit
        chunks = chunk_dialogues(dialogues)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 2)
        self.assertEqual(len(chunks[1]), 2)

        # Test chunking with custom limit
        chunks = chunk_dialogues(dialogues, limit=8000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 4)

        # Test with empty dialogues
        chunks = chunk_dialogues([])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 0)

    def test_pre_translate_store(self):
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a test file path
            test_file_path = os.path.join(test_dir, "test_subtitle.srt")
            open(test_file_path, "w").close()

            # Test saving and loading pre-translate store
            pre_translate_context = [
                PreTranslatedContext(
                    original="Hello", translated="Hola", description="Greeting"
                ),
                PreTranslatedContext(
                    original="World", translated="Mundo", description="Place"
                ),
            ]

            # Save the pre-translate store
            save_pre_translate_store(test_file_path, pre_translate_context)

            # Check if the store file was created
            store_path = os.path.join(
                test_dir, ".translate", "pre_translate_store.json"
            )
            self.assertTrue(os.path.exists(store_path))

            # Load the pre-translate store
            loaded_context = load_pre_translate_store(test_file_path)
            self.assertEqual(len(loaded_context), 2)
            self.assertEqual(loaded_context[0]["original"], "Hello")
            self.assertEqual(loaded_context[0]["translated"], "Hola")
            self.assertEqual(loaded_context[1]["original"], "World")
            self.assertEqual(loaded_context[1]["translated"], "Mundo")
