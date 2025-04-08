import unittest
import asyncio
from unittest.mock import patch, MagicMock
from main import translate_file, translate_prepare
from format.format import SubtitleFormat
from subtitle_types import RichSubtitleDialogue, SubtitleDialogue, PreTranslatedContext


class TestTranslateFile(unittest.TestCase):
    def setUp(self):
        # Create a mock SubtitleFormat for testing
        self.mock_subtitle_format = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for testing
        self.sample_dialogues = [
            RichSubtitleDialogue(id=1, content="Hello", actor="John", style="Default"),
            RichSubtitleDialogue(id=2, content="World", actor="Jane", style="Default"),
            RichSubtitleDialogue(id=3, content="Test", actor="John", style="Default"),
        ]

        # Sample pre-translated context
        self.pre_translated_context = [
            PreTranslatedContext(
                original="John", translated="Juan", description="Character name"
            ),
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
        ]

        # Configure the mock to return our sample dialogues
        self.mock_subtitle_format.dialogues.return_value = self.sample_dialogues

    @patch("main.chunk_dialogues")
    @patch("main.translate_dialouges")
    async def test_translate_file_basic(
        self, mock_translate_dialogues, mock_chunk_dialogues
    ):
        # Configure mocks
        mock_chunk_dialogues.return_value = [self.sample_dialogues]

        # Mock the translated dialogues that would be returned by translate_dialogues
        translated_dialogues = [
            SubtitleDialogue(id=1, content="Hola"),
            SubtitleDialogue(id=2, content="Mundo"),
            SubtitleDialogue(id=3, content="Prueba"),
        ]

        # Set up the mock to return our translated dialogues when called
        mock_translate_dialogues.return_value = translated_dialogues

        # Call the function being tested
        result = await translate_file(
            self.mock_subtitle_format, "Spanish", self.pre_translated_context
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with(self.sample_dialogues, 5000)
        mock_translate_dialogues.assert_called_once()
        self.mock_subtitle_format.update.assert_called_once_with(translated_dialogues)
        self.assertEqual(result, self.mock_subtitle_format)

    @patch("main.chunk_dialogues")
    @patch("main.translate_dialouges")
    @patch("os.environ")
    async def test_translate_file_with_verbose(
        self, mock_environ, mock_translate_dialogues, mock_chunk_dialogues
    ):
        # Configure environment to enable verbose mode
        mock_environ.get.return_value = "1"

        # Configure mocks
        mock_chunk_dialogues.return_value = [self.sample_dialogues]

        # Mock the translated dialogues
        translated_dialogues = [
            SubtitleDialogue(id=1, content="Hola"),
            SubtitleDialogue(id=2, content="Mundo"),
            SubtitleDialogue(id=3, content="Prueba"),
        ]

        mock_translate_dialogues.return_value = translated_dialogues

        # Call the function being tested
        result = await translate_file(
            self.mock_subtitle_format, "Spanish", self.pre_translated_context
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with(self.sample_dialogues, 5000)
        mock_translate_dialogues.assert_called_once()
        self.mock_subtitle_format.update.assert_called_once_with(translated_dialogues)
        self.assertEqual(result, self.mock_subtitle_format)

    @patch("main.chunk_dialogues")
    @patch("main.translate_dialouges")
    async def test_translate_file_multiple_chunks(
        self, mock_translate_dialogues, mock_chunk_dialogues
    ):
        # Split dialogues into two chunks
        chunk1 = [self.sample_dialogues[0], self.sample_dialogues[1]]
        chunk2 = [self.sample_dialogues[2]]
        mock_chunk_dialogues.return_value = [chunk1, chunk2]

        # Mock the translated dialogues for each chunk
        translated_chunk1 = [
            SubtitleDialogue(id=1, content="Hola"),
            SubtitleDialogue(id=2, content="Mundo"),
        ]
        translated_chunk2 = [
            SubtitleDialogue(id=3, content="Prueba"),
        ]

        # Set up the mock to return our translated dialogues when called
        mock_translate_dialogues.side_effect = [translated_chunk1, translated_chunk2]

        # Call the function being tested
        result = await translate_file(
            self.mock_subtitle_format, "Spanish", self.pre_translated_context
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with(self.sample_dialogues, 5000)
        self.assertEqual(mock_translate_dialogues.call_count, 2)

        # Check that update was called for each chunk
        self.assertEqual(self.mock_subtitle_format.update.call_count, 2)
        self.mock_subtitle_format.update.assert_any_call(translated_chunk1)
        self.mock_subtitle_format.update.assert_any_call(translated_chunk2)

        self.assertEqual(result, self.mock_subtitle_format)

    @patch("main.translate_context")
    @patch("main.chunk_dialogues")
    async def test_translate_prepare_basic(
        self, mock_chunk_dialogues, mock_translate_context
    ):
        # Create a second mock subtitle format
        mock_subtitle_format2 = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for the second format
        sample_dialogues2 = [
            RichSubtitleDialogue(id=4, content="Another", actor="Bob", style="Default"),
            RichSubtitleDialogue(
                id=5, content="Example", actor="Alice", style="Default"
            ),
        ]

        # Configure the mocks to return our sample dialogues
        self.mock_subtitle_format.dialogues.return_value = self.sample_dialogues
        mock_subtitle_format2.dialogues.return_value = sample_dialogues2

        # Configure chunk_dialogues to return a single chunk with all dialogues
        all_dialogues = self.sample_dialogues + sample_dialogues2
        mock_chunk_dialogues.return_value = [all_dialogues]

        # Mock the context that would be returned by translate_context
        context_result = [
            PreTranslatedContext(
                original="John", translated="Juan", description="Character name"
            ),
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
            PreTranslatedContext(
                original="Bob", translated="Roberto", description="Character name"
            ),
            PreTranslatedContext(
                original="Alice", translated="Alicia", description="Character name"
            ),
        ]

        # Set up the mock to return our context when called
        mock_translate_context.return_value = context_result

        # Call the function being tested
        result = await translate_prepare(
            [self.mock_subtitle_format, mock_subtitle_format2], "Spanish"
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with(all_dialogues, 50000)
        mock_translate_context.assert_called_once()

        # Check that the result contains all the expected context items
        self.assertEqual(result, context_result)

    @patch("main.translate_context")
    @patch("main.chunk_dialogues")
    async def test_translate_prepare_multiple_chunks(
        self, mock_chunk_dialogues, mock_translate_context
    ):
        # Create a second mock subtitle format
        mock_subtitle_format2 = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for the second format
        sample_dialogues2 = [
            RichSubtitleDialogue(id=4, content="Another", actor="Bob", style="Default"),
            RichSubtitleDialogue(
                id=5, content="Example", actor="Alice", style="Default"
            ),
        ]

        # Configure the mocks to return our sample dialogues
        self.mock_subtitle_format.dialogues.return_value = self.sample_dialogues
        mock_subtitle_format2.dialogues.return_value = sample_dialogues2

        # Configure chunk_dialogues to return multiple chunks
        chunk1 = self.sample_dialogues
        chunk2 = sample_dialogues2
        mock_chunk_dialogues.return_value = [chunk1, chunk2]

        # Mock the context that would be returned by translate_context for each chunk
        context_result1 = [
            PreTranslatedContext(
                original="John", translated="Juan", description="Character name"
            ),
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
        ]

        context_result2 = [
            PreTranslatedContext(
                original="Bob", translated="Roberto", description="Character name"
            ),
            PreTranslatedContext(
                original="Alice", translated="Alicia", description="Character name"
            ),
        ]

        # Set up the mock to return our context when called
        mock_translate_context.side_effect = [context_result1, context_result2]

        # Call the function being tested
        result = await translate_prepare(
            [self.mock_subtitle_format, mock_subtitle_format2], "Spanish"
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once()
        self.assertEqual(mock_translate_context.call_count, 2)

        # Check that the result contains all the expected context items from both chunks
        expected_result = context_result1 + context_result2
        self.assertEqual(result, expected_result)

    @patch("main.translate_context")
    @patch("main.chunk_dialogues")
    async def test_translate_prepare_empty_input(
        self, mock_chunk_dialogues, mock_translate_context
    ):
        # Configure chunk_dialogues to return an empty list
        mock_chunk_dialogues.return_value = []

        # Call the function being tested with an empty list of subtitle formats
        result = await translate_prepare([], "Spanish")

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with([], 50000)
        mock_translate_context.assert_not_called()

        # Check that the result is an empty list
        self.assertEqual(result, [])


def run_async_test(coro):
    return asyncio.run(coro)


# Helper to run async tests
def async_test(test_case):
    def wrapper(*args, **kwargs):
        return run_async_test(test_case(*args, **kwargs))

    return wrapper


# Apply the async_test decorator to the test methods
TestTranslateFile.test_translate_file_basic = async_test(
    TestTranslateFile.test_translate_file_basic
)
TestTranslateFile.test_translate_file_with_verbose = async_test(
    TestTranslateFile.test_translate_file_with_verbose
)
TestTranslateFile.test_translate_file_multiple_chunks = async_test(
    TestTranslateFile.test_translate_file_multiple_chunks
)

# Apply the async_test decorator to the new test methods
TestTranslateFile.test_translate_prepare_basic = async_test(
    TestTranslateFile.test_translate_prepare_basic
)
TestTranslateFile.test_translate_prepare_multiple_chunks = async_test(
    TestTranslateFile.test_translate_prepare_multiple_chunks
)
TestTranslateFile.test_translate_prepare_empty_input = async_test(
    TestTranslateFile.test_translate_prepare_empty_input
)
