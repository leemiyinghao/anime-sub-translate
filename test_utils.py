import os
import tempfile
import unittest

from subtitle_types import SubtitleDialogue
from utils import (
    best_match,
    chunk_dialogues,
    dialogue_remap_id,
    dialogue_remap_id_reverse,
    find_files_from_path,
    levenshtein_distance,
    read_subtitle_file,
    string_similarity,
)


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
            sub_dir = os.path.join(test_dir, "sub")
            os.makedirs(sub_dir, exist_ok=True)
            sub_srt_file_path = os.path.join(sub_dir, "test_sub_subtitle.srt")

            open(srt_file_path, "w").close()
            open(ssa_file_path, "w").close()
            open(ass_file_path, "w").close()
            open(txt_file_path, "w").close()
            open(sub_srt_file_path, "w").close()

            # Test find_files_from_path
            files = find_files_from_path(test_dir, "")
            self.assertEqual(len(files), 4)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(sub_srt_file_path in files)

            self.assertTrue(ssa_file_path in files)
            self.assertTrue(ass_file_path in files)

            # Test with ignore_postfix
            files = find_files_from_path(test_dir, "translated")
            self.assertEqual(len(files), 3)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(ass_file_path in files)

            # Test with match_postfix
            files = find_files_from_path(test_dir, "", match_postfix="subtitle")
            self.assertEqual(len(files), 3)
            self.assertTrue(srt_file_path in files)
            self.assertTrue(sub_srt_file_path in files)
            self.assertTrue(ass_file_path in files)

    def test_chunk_dialogues(self):
        # Create sample dialogues
        dialogues = [
            SubtitleDialogue(id="1", content="A" * 2000, actor="John", style="Default"),
            SubtitleDialogue(id="2", content="B" * 2000, actor="Jane", style="Default"),
            SubtitleDialogue(id="3", content="C" * 2000, actor="John", style="Default"),
            SubtitleDialogue(id="4", content="D" * 2000, actor="Jane", style="Default"),
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

    def test_dialogue_remap_id(self):
        dialogues = [
            SubtitleDialogue(id="123", content="Hello", actor="John", style="Default"),
            SubtitleDialogue(id="456", content="World", actor="Jane", style="Default"),
        ]

        remapped_dialogues, id_mapping = dialogue_remap_id(dialogues)

        self.assertEqual(len(remapped_dialogues), 2)
        self.assertEqual(remapped_dialogues[0].id, "0")
        self.assertEqual(remapped_dialogues[1].id, "1")
        self.assertEqual(id_mapping, {"0": "123", "1": "456"})

    def test_dialogue_remap_id_reverse(self):
        dialogues = [
            SubtitleDialogue(id="0", content="Hello", actor="John", style="Default"),
            SubtitleDialogue(id="1", content="World", actor="Jane", style="Default"),
        ]
        id_mapping = {"0": "123", "1": "456"}

        remapped_dialogues = dialogue_remap_id_reverse(dialogues, id_mapping)

        self.assertEqual(len(remapped_dialogues), 2)
        self.assertEqual(remapped_dialogues[0].id, "123")
        self.assertEqual(remapped_dialogues[1].id, "456")

    def test_string_similarity_identical(self):
        self.assertEqual(string_similarity("hello", "hello"), 1.0)

    def test_string_similarity_empty(self):
        self.assertEqual(string_similarity("", ""), 0.0)
        self.assertEqual(string_similarity("hello", ""), 0.0)
        self.assertEqual(string_similarity("", "hello"), 0.0)

    def test_string_similarity_partial(self):
        self.assertAlmostEqual(string_similarity("abc", "abd"), 2 / 3)

    def test_string_similarity_different(self):
        self.assertEqual(string_similarity("abc", "def"), 0.0)

    def test_string_similarity_case_insensitive(self):
        self.assertAlmostEqual(string_similarity("Hello", "hello"), 1.0)


class TestLevenshteinDistance(unittest.TestCase):
    def test_levenshtein_distance_identical(self):
        self.assertEqual(levenshtein_distance("hello", "hello"), 0)

    def test_levenshtein_distance_empty(self):
        self.assertEqual(levenshtein_distance("", ""), 0)
        self.assertEqual(levenshtein_distance("hello", ""), 5)
        self.assertEqual(levenshtein_distance("", "hello"), 5)

    def test_levenshtein_distance_substitution(self):
        self.assertEqual(levenshtein_distance("abc", "abd"), 1)

    def test_levenshtein_distance_insertion(self):
        self.assertEqual(levenshtein_distance("abc", "abdc"), 1)

    def test_levenshtein_distance_deletion(self):
        self.assertEqual(levenshtein_distance("abc", "ab"), 1)


class TestBestMatch(unittest.TestCase):
    def test_best_match_empty_candidates(self):
        self.assertIsNone(best_match("test", [], key=lambda x: x))

    def test_best_match_identical(self):
        candidates = ["hello", "world", "test"]
        self.assertEqual(best_match("test", candidates, key=lambda x: x), "test")

    def test_best_match_partial(self):
        candidates = ["hello", "world", "testing"]
        self.assertEqual(best_match("test", candidates, key=lambda x: x), "testing")

    def test_best_match_no_match(self):
        candidates = ["hello", "world", "python"]
        self.assertIsNone(best_match("test", candidates, key=lambda x: x))

    def test_best_match_threshold(self):
        candidates = ["hello", "world", "testing"]
        self.assertIsNone(
            best_match("test", candidates, key=lambda x: x, threshold=0.8)
        )

    def test_best_match_key(self):
        candidates = [{"name": "hello"}, {"name": "world"}, {"name": "testing"}]
        self.assertEqual(
            best_match("test", candidates, key=lambda x: x["name"]), {"name": "testing"}
        )

    def test_best_match_multiple_candidate_strings(self):
        candidates = ["hello", "world", "testing", "test2"]

        def key(x):
            if x == "test2":
                return ["test", "test2"]
            else:
                return x

        self.assertEqual(best_match("test", candidates, key=key), "test2")


if __name__ == "__main__":
    unittest.main()
