import asyncio
import unittest
from unittest.mock import ANY, MagicMock, call, patch

from format.format import SubtitleFormat
from subtitle_types import PreTranslatedContext, SubtitleDialogue
from translate import (
    TaskParameter,
    _prepare_context,
    default_tasks,
    task_prepare_context,
    task_prepare_metadata,
    task_translate_files,
    translate,
    translate_file,
)


class TestTranslate(unittest.TestCase):
    def setUp(self):
        # Create a mock SubtitleFormat for testing
        self.mock_subtitle_format = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for testing
        self.sample_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor="John", style="Default"),
            SubtitleDialogue(id="2", content="World", actor="Jane", style="Default"),
            SubtitleDialogue(id="3", content="Test", actor="John", style="Default"),
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

    @patch("translate.dialogue_remap_id_reverse")
    @patch("translate.dialogue_remap_id")
    @patch("translate.chunk_dialogues")
    @patch("translate.translate_dialogues")
    async def test_translate_file_basic(
        self,
        mock_translate_dialogues,
        mock_chunk_dialogues,
        mock_remap_id,
        mock_remap_id_reverse,
    ):
        # Configure mocks
        mock_chunk_dialogues.return_value = [self.sample_dialogues]
        mock_remap_id.side_effect = lambda x: (x, {})
        mock_remap_id_reverse.side_effect = lambda x, _: (x)

        # Mock the translated dialogues that would be returned by translate_dialogues
        translated_dialogues = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
            SubtitleDialogue(id="3", content="Prueba"),
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

    @patch("translate.dialogue_remap_id_reverse")
    @patch("translate.dialogue_remap_id")
    @patch("translate.chunk_dialogues")
    @patch("translate.translate_dialogues")
    async def test_translate_file_multiple_chunks(
        self,
        mock_translate_dialogues,
        mock_chunk_dialogues,
        mock_remap_id,
        mock_remap_id_reverse,
    ):
        # Split dialogues into two chunks
        chunk1 = [self.sample_dialogues[0], self.sample_dialogues[1]]
        chunk2 = [self.sample_dialogues[2]]
        mock_chunk_dialogues.return_value = [chunk1, chunk2]
        mock_remap_id.side_effect = lambda x: (x, {})
        mock_remap_id_reverse.side_effect = lambda x, _: (x)

        # Mock the translated dialogues for each chunk
        translated_chunk1 = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
        ]
        translated_chunk2 = [
            SubtitleDialogue(id="3", content="Prueba"),
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

    @patch("translate.translate_context")
    @patch("translate.refine_context")
    @patch("translate.chunk_dialogues")
    async def test_translate_prepare_basic(
        self, mock_chunk_dialogues, mock_refine_context, mock_translate_context
    ):
        # Create a second mock subtitle format
        mock_subtitle_format2 = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for the second format
        sample_dialogues2 = [
            SubtitleDialogue(id="4", content="Another", actor="Bob", style="Default"),
            SubtitleDialogue(id="5", content="Example", actor="Alice", style="Default"),
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
        mock_refine_context.return_value = context_result

        # Call the function being tested
        result = await _prepare_context(
            [self.mock_subtitle_format, mock_subtitle_format2], "Spanish"
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with(all_dialogues, 500000)
        mock_translate_context.assert_called_once()
        mock_refine_context.assert_called_once()

        # Check that the result contains all the expected context items
        self.assertEqual(result, context_result)

    @patch("translate.translate_context")
    @patch("translate.refine_context")
    @patch("translate.chunk_dialogues")
    async def test_translate_prepare_multiple_chunks(
        self, mock_chunk_dialogues, mock_refine_context, mock_translate_context
    ):
        # Create a second mock subtitle format
        mock_subtitle_format2 = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for the second format
        sample_dialogues2 = [
            SubtitleDialogue(id="4", content="Another", actor="Bob", style="Default"),
            SubtitleDialogue(id="5", content="Example", actor="Alice", style="Default"),
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
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
            # duplicated
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
        ]

        expected_result = [
            PreTranslatedContext(
                original="Bob", translated="Roberto", description="Character name"
            ),
            PreTranslatedContext(
                original="Alice", translated="Alicia", description="Character name"
            ),
            PreTranslatedContext(
                original="Jane", translated="Juana", description="Character name"
            ),
            PreTranslatedContext(
                original="John", translated="Juan", description="Character name"
            ),
        ]

        # Set up the mock to return our context when called
        mock_translate_context.side_effect = [context_result1, context_result2]
        mock_refine_context.return_value = expected_result

        # Call the function being tested
        result = await _prepare_context(
            [self.mock_subtitle_format, mock_subtitle_format2], "Spanish"
        )

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once()
        self.assertEqual(mock_translate_context.call_count, 2)
        self.maxDiff = None
        self.assertEqual(
            sorted(
                mock_refine_context.call_args.kwargs["contexts"],
                key=lambda c: c.original,
            ),
            sorted(expected_result, key=lambda c: c.original),
        )

        # Check that the result contains all the expected context items from both chunks
        self.assertEqual(result, expected_result)

    @patch("translate.translate_context")
    @patch("translate.refine_context")
    @patch("translate.chunk_dialogues")
    async def test_translate_prepare_empty_input(
        self,
        mock_chunk_dialogues,
        mock_refine_context,
        mock_translate_context,
    ):
        # Configure chunk_dialogues to return an empty list
        mock_chunk_dialogues.return_value = []
        mock_refine_context.return_value = []

        # Call the function being tested with an empty list of subtitle formats
        result = await _prepare_context([], "Spanish")

        # Verify the function behaved as expected
        mock_chunk_dialogues.assert_called_once_with([], 500000)
        mock_translate_context.assert_not_called()
        mock_refine_context.assert_called_once()  # refine_context should be called even if empty
        # Check that the result is an empty list
        self.assertEqual(result, [])

    @patch("translate.load_pre_translate_store")
    @patch("translate._prepare_context")
    @patch("translate.save_pre_translate_store")
    async def test_task_prepare_context_no_existing_context(
        self,
        mock_save_pre_translate_store,
        mock__prepare_context,
        mock_load_pre_translate_store,
    ):
        # Mock the TaskParameter
        mock_load_pre_translate_store.return_value = None
        mock__prepare_context.return_value = self.pre_translated_context

        # Create a mock SubtitleFormat for testing
        self.mock_subtitle_format = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for testing
        self.sample_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor="John", style="Default"),
            SubtitleDialogue(id="2", content="World", actor="Jane", style="Default"),
            SubtitleDialogue(id="3", content="Test", actor="John", style="Default"),
        ]

        # Configure the mock to return our sample dialogues
        self.mock_subtitle_format.dialogues.return_value = self.sample_dialogues

        mock_task_parameter = MagicMock()
        mock_task_parameter.base_path = "/path/to/subtitles"
        mock_task_parameter.target_language = "Spanish"
        mock_task_parameter.pre_translated_context = None
        mock_task_parameter.subtitle_paths = ["/path/to/subtitle1.srt"]
        mock_task_parameter.update.return_value = mock_task_parameter

        # Mock read_subtitle_file to return a known content
        with (
            patch("translate.parse_subtitle_file") as mock_parse_subtitle_file,
            patch("translate.find_files_from_path") as mock_find_files_from_path,
        ):
            mock_parse_subtitle_file.return_value = self.mock_subtitle_format
            mock_find_files_from_path.return_value = ["/path/to/subtitle1.srt"]

            result = await task_prepare_context(mock_task_parameter)

        # Assertions
        mock_load_pre_translate_store.assert_called_once_with("/path/to/subtitles")
        mock__prepare_context.assert_called_once()
        mock_save_pre_translate_store.assert_called_once_with(
            "/path/to/subtitles", self.pre_translated_context
        )
        mock_task_parameter.update.assert_called_once_with(
            pre_translated_context=self.pre_translated_context
        )
        self.assertEqual(result, mock_task_parameter)

    @patch("translate.load_pre_translate_store")
    @patch("translate._prepare_context")
    @patch("translate.save_pre_translate_store")
    async def test_task_prepare_context_existing_context(
        self,
        mock_save_pre_translate_store,
        mock__prepare_context,
        mock_load_pre_translate_store,
    ):
        # Mock the TaskParameter
        mock_load_pre_translate_store.return_value = self.pre_translated_context

        # Create a mock SubtitleFormat for testing
        self.mock_subtitle_format = MagicMock(spec=SubtitleFormat)

        # Sample dialogues for testing
        self.sample_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor="John", style="Default"),
            SubtitleDialogue(id="2", content="World", actor="Jane", style="Default"),
            SubtitleDialogue(id="3", content="Test", actor="John", style="Default"),
        ]

        # Configure the mock to return our sample dialogues
        self.mock_subtitle_format.dialogues.return_value = self.sample_dialogues

        mock_task_parameter = MagicMock()
        mock_task_parameter.base_path = "/path/to/subtitles"
        mock_task_parameter.target_language = "Spanish"
        mock_task_parameter.pre_translated_context = None
        mock_task_parameter.subtitle_paths = ["/path/to/subtitle1.srt"]
        mock_task_parameter.update.return_value = mock_task_parameter

        result = await task_prepare_context(mock_task_parameter)

        # Assertions
        mock_load_pre_translate_store.assert_called_once_with("/path/to/subtitles")
        mock__prepare_context.assert_not_called()
        mock_save_pre_translate_store.assert_not_called()
        mock_task_parameter.update.assert_called_once_with(
            pre_translated_context=self.pre_translated_context
        )
        self.assertEqual(result, mock_task_parameter)

    @patch("translate.os.path.exists")
    @patch("translate.write_translated_subtitle")
    @patch("translate.get_output_path")
    @patch("translate.parse_subtitle_file")
    @patch("translate.translate_file")
    async def test_task_translate_files(
        self,
        mock_translate_file,
        mock_parse_subtitle_file,
        mock_get_output_path,
        mock_write_translated_subtitle,
        mock_os_path_exists,
    ):
        # Mock the TaskParameter
        mock_task_parameter = MagicMock()
        mock_task_parameter.base_path = "/path/to/subtitles"
        mock_task_parameter.target_language = "Spanish"
        mock_task_parameter.pre_translated_context = self.pre_translated_context
        mock_task_parameter.subtitle_paths = ["/path/to/subtitle1.srt"]

        # Mock parse_subtitle_file to return a mock SubtitleFormat
        mock_subtitle_format = MagicMock(spec=SubtitleFormat)
        mock_parse_subtitle_file.return_value = mock_subtitle_format

        # Mock translate_file to return the same mock SubtitleFormat
        mock_translate_file.return_value = mock_subtitle_format

        # Mock get_output_path to return a test output path
        mock_get_output_path.return_value = "/path/to/output.srt"

        # Mock os.path.exists to return False (file does not exist)
        mock_os_path_exists.return_value = False

        mock_task_parameter = MagicMock()
        mock_task_parameter.base_path = "/path/to/subtitles"
        mock_task_parameter.target_language = "Spanish"
        mock_task_parameter.pre_translated_context = self.pre_translated_context
        mock_task_parameter.subtitle_paths = ["/path/to/subtitle1.srt"]
        mock_task_parameter.update.return_value = mock_task_parameter
        result = await task_translate_files(mock_task_parameter)

        # Assertions
        mock_parse_subtitle_file.assert_called_once_with("/path/to/subtitle1.srt")
        mock_translate_file.assert_called_once_with(
            mock_subtitle_format,
            mock_task_parameter.target_language,
            mock_task_parameter.pre_translated_context,
            metadata=mock_task_parameter.metadata,
        )
        mock_get_output_path.assert_called_once_with(
            "/path/to/subtitle1.srt", "Spanish"
        )
        mock_write_translated_subtitle.assert_called_once()
        self.assertEqual(result, mock_task_parameter)

    @patch("translate.save_media_set_metadata")
    @patch("translate.prepare_metadata")
    @patch("translate.load_media_set_metadata")
    async def test_task_prepare_metadata_no_existing_metadata(
        self,
        mock_load_media_set_metadata,
        mock_prepare_metadata,
        mock_save_media_set_metadata,
    ):
        # Mock the TaskParameter
        mock_task_parameter = MagicMock()
        mock_task_parameter.base_path = "/path/to/subtitles"

        # Mock load_media_set_metadata to return None (no existing metadata)
        mock_load_media_set_metadata.return_value = None

        # Mock prepare_metadata to return a mock MediaSetMetadata
        mock_metadata = MagicMock()
        mock_prepare_metadata.return_value = mock_metadata

        task_param = TaskParameter(
            base_path="/path/to/subtitles", target_language="Spanish"
        )
        result = await task_prepare_metadata(task_param)

        # Assertions
        mock_load_media_set_metadata.assert_called_once_with("/path/to/subtitles")
        mock_prepare_metadata.assert_called_once_with("/path/to/subtitles")
        mock_save_media_set_metadata.assert_called_once_with(
            "/path/to/subtitles", mock_metadata
        )
        self.assertEqual(result.metadata, mock_metadata)

    @patch("translate.asyncio.run")
    @patch("translate.Speedometer")
    @patch("translate.tqdm")
    @patch("translate.current_progress")
    @patch("translate.os.path.isdir")
    @patch("translate.TaskParameter")
    def test_translate(
        self,
        mock_task_parameter,
        mock_os_path_isdir,
        mock_current_progress,
        mock_tqdm,
        mock_speedometer,
        mock_asyncio_run,
    ):
        # Mock necessary objects and functions
        mock_os_path_isdir.return_value = True
        mock_task_parameter_instance = MagicMock()
        mock_task_parameter.return_value = mock_task_parameter_instance
        mock_speedometer_instance = MagicMock()
        mock_speedometer.return_value = mock_speedometer_instance
        mock_progress_instance = MagicMock()
        mock_current_progress.return_value = mock_progress_instance

        translate("/path/to/subtitles/", "Spanish", default_tasks)

        # Assertions
        mock_task_parameter.assert_called_once_with(
            base_path="/path/to/subtitles/",
            target_language="Spanish",
            set_description=ANY,
            metadata=ANY,
            pre_translated_context=ANY,
        )
        expected_calls = [call(ANY) for _ in default_tasks]
        mock_asyncio_run.assert_has_calls(expected_calls)
        self.assertEqual(mock_asyncio_run.call_count, len(default_tasks))


def run_async_test(coro):
    return asyncio.run(coro)


# Helper to run async tests
def async_test(test_case):
    def wrapper(*args, **kwargs):
        return run_async_test(test_case(*args, **kwargs))

    return wrapper


TestTranslate.test_translate_file_basic = async_test(
    TestTranslate.test_translate_file_basic
)
TestTranslate.test_translate_file_multiple_chunks = async_test(
    TestTranslate.test_translate_file_multiple_chunks
)
TestTranslate.test_translate_prepare_basic = async_test(
    TestTranslate.test_translate_prepare_basic
)
TestTranslate.test_translate_prepare_multiple_chunks = async_test(
    TestTranslate.test_translate_prepare_multiple_chunks
)
TestTranslate.test_translate_prepare_empty_input = async_test(
    TestTranslate.test_translate_prepare_empty_input
)
TestTranslate.test_task_prepare_context_existing_context = async_test(
    TestTranslate.test_task_prepare_context_existing_context
)
TestTranslate.test_task_prepare_context_no_existing_context = async_test(
    TestTranslate.test_task_prepare_context_no_existing_context
)
TestTranslate.test_task_prepare_metadata_no_existing_metadata = async_test(
    TestTranslate.test_task_prepare_metadata_no_existing_metadata
)
TestTranslate.test_task_translate_files = async_test(
    TestTranslate.test_task_translate_files
)
