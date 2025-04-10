import os
import tempfile
import unittest

from store import (
    load_pre_translate_store,
    save_pre_translate_store,
)
from subtitle_types import PreTranslatedContext


class TestStore(unittest.TestCase):
    def test_roundtrip(self):
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
            self.assertEqual(loaded_context, pre_translate_context)


if __name__ == "__main__":
    unittest.main()
