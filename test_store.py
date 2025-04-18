import os
import tempfile
import unittest

from store import (
    load_media_set_metadata,
    load_pre_translate_store,
    save_media_set_metadata,
    save_pre_translate_store,
)
from subtitle_types import (
    CharacterInfo,
    Metadata,
    TermBank,
    TermBankItem,
)


class TestStore(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a test file path
            test_file_path = os.path.join(test_dir, "test_subtitle.srt")
            open(test_file_path, "w").close()

            term_bank = TermBank(
                context={
                    "Hello": TermBankItem(translated="你好"),
                    "Goodbye": TermBankItem(translated="再見"),
                }
            )
            # Save the pre-translate store
            save_pre_translate_store(test_file_path, term_bank)

            # Check if the store file was created
            store_path = os.path.join(
                test_dir, ".translate", "pre_translate_store.json"
            )
            self.assertTrue(os.path.exists(store_path))

            # Load the pre-translate store
            loaded_context = load_pre_translate_store(test_file_path)
            self.assertEqual(loaded_context, term_bank)

    def test_media_set_metadata_roundtrip(self):
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a test file path
            test_file_path = os.path.join(test_dir, "test_subtitle.srt")
            open(test_file_path, "w").close()

            # Create a sample MediaSetMetadata object
            metadata = Metadata(
                title="Test Title",
                title_alt=["Alternative Title"],
                description="Test Description",
                characters=[CharacterInfo(name="Test Character", gender="Unknown")],
            )

            # Save the media set metadata
            save_media_set_metadata(test_file_path, metadata)

            # Check if the store file was created
            store_path = os.path.join(
                test_dir, ".translate", "pre_translate_store.json"
            )
            self.assertTrue(os.path.exists(store_path))

            # Load the media set metadata
            loaded_metadata = load_media_set_metadata(test_file_path)
            self.assertEqual(loaded_metadata, metadata)


if __name__ == "__main__":
    unittest.main()
