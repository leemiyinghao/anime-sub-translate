import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from setting import _Setting, set_setting
from subtitle_types import PreTranslatedContext, SubtitleDialogue

from .base import (
    FailedAfterRetries,
    _simple_sanity_check,
    translate_context,
    translate_dialogues,
)
from .dto import (
    PreTranslatedContextSetDTO,
)


class TestLLM(unittest.TestCase):
    def setUp(self):
        # Reduce retry wait time for tests
        set_setting(_Setting(llm_retry_times=2, llm_retry_delay=0))

    def test_simple_sanity_check_matching_ids(self):
        # Test case where original and translated dialogues have the same IDs
        original = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
            SubtitleDialogue(id="3", content="Test", actor=None, style=None),
        ]

        translated = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
            SubtitleDialogue(id="3", content="Prueba"),
        ]

        self.assertTrue(_simple_sanity_check(original, translated))

    def test_simple_sanity_check_different_ids(self):
        # Test case where original and translated dialogues have different IDs
        original = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
            SubtitleDialogue(id="3", content="Test", actor=None, style=None),
        ]

        translated = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
            SubtitleDialogue(id="4", content="Prueba"),  # Different ID (4 instead of 3)
        ]

        self.assertFalse(_simple_sanity_check(original, translated))

    def test_simple_sanity_check_missing_ids(self):
        # Test case where translated dialogues are missing some IDs
        original = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
            SubtitleDialogue(id="3", content="Test", actor=None, style=None),
        ]

        translated = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="3", content="Prueba"),  # Missing ID 2
        ]

        self.assertFalse(_simple_sanity_check(original, translated))

    def test_simple_sanity_check_extra_ids(self):
        # Test case where translated dialogues have extra IDs
        original = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
        ]

        translated = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
            SubtitleDialogue(id="3", content="Extra"),  # Extra ID
        ]

        self.assertFalse(_simple_sanity_check(original, translated))

    def test_simple_sanity_check_empty_inputs(self):
        # Test case with empty inputs
        original = []
        translated = []

        self.assertTrue(_simple_sanity_check(original, translated))

    def test_simple_sanity_check_different_order(self):
        # Test case where IDs are the same but in different order
        original = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
            SubtitleDialogue(id="3", content="Test", actor=None, style=None),
        ]

        translated = [
            SubtitleDialogue(id="3", content="Prueba"),
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
        ]

        # This should pass since we're only checking if the sets of IDs match
        self.assertTrue(_simple_sanity_check(original, translated))

    @patch("llm.base._send_llm_request")
    def test_translate_context_success(self, mock_send_llm_request):
        # Setup mock response with a proper async generator function
        async def mock_generator(*args, **kwargs):
            response = json.dumps(
                {
                    "context": [
                        {
                            "original": "John",
                            "translated": "John",
                            "description": "Character name",
                        },
                        {
                            "original": "Tokyo",
                            "translated": "Tokio",
                            "description": "City name",
                        },
                    ]
                }
            )
            for char in response:
                yield char

        expected = [
            PreTranslatedContext(
                original="John", translated="John", description="Character name"
            ),
            PreTranslatedContext(
                original="Tokyo", translated="Tokio", description="City name"
            ),
        ]

        # Reset the mock to avoid side effects from other tests
        mock_send_llm_request.reset_mock()
        mock_send_llm_request.side_effect = mock_generator

        # Test data
        original_dialogues = [
            SubtitleDialogue(
                id="1", content="John went to Tokyo", actor=None, style=None
            ),
            SubtitleDialogue(
                id="2", content="Tokyo is beautiful", actor=None, style=None
            ),
        ]

        # Run the test
        result = asyncio.run(
            translate_context(original=original_dialogues, target_language="Spanish")
        )

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(
            result,
            expected,
        )

        # Verify the mock was called with the right parameters
        mock_send_llm_request.assert_called_once()

    @patch("llm.base._send_llm_request")
    def test_translate_context_with_previous_translated(self, mock_send_llm_request):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps(
                {
                    "context": [
                        {
                            "original": "John",
                            "translated": "John",
                            "description": "Character name",
                        },
                        {
                            "original": "Tokyo",
                            "translated": "Tokio",
                            "description": "City name",
                        },
                        {
                            "original": "Sakura",
                            "translated": "Sakura",
                            "description": "Character name",
                        },
                    ]
                }
            )
            for char in response:
                yield char

        # Reset the mock to avoid side effects from other tests
        mock_send_llm_request.reset_mock()
        mock_send_llm_request.side_effect = mock_generator

        # Test data
        original_dialogues = [
            SubtitleDialogue(
                id="1", content="John and Sakura went to Tokyo", actor=None, style=None
            )
        ]

        previous_translated = [
            PreTranslatedContext(
                original="John", translated="John", description="Character name"
            ),
            PreTranslatedContext(
                original="Tokyo", translated="Tokio", description="City name"
            ),
        ]

        # Run the test
        asyncio.run(
            translate_context(
                original=original_dialogues,
                target_language="Spanish",
                previous_translated=previous_translated,
            )
        )

        # Verify the mock was called with the right parameters
        mock_send_llm_request.assert_called_once()
        # Check that the system message includes instructions about previous context
        _, kwargs = mock_send_llm_request.call_args
        self.assertTrue(
            any("previous context" in msg for msg in kwargs["instructions"])
        )

    @patch("llm.base._send_llm_request")
    def test_translate_context_with_progress_bar(self, mock_send_llm_request):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps(
                {"context": [{"original": "John", "translated": "John"}]}
            )
            for char in response:
                yield char

        # Reset the mock to avoid side effects from other tests
        mock_send_llm_request.reset_mock()
        mock_send_llm_request.side_effect = mock_generator

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello John", actor=None, style=None)
        ]

        # Mock progress bar - use MagicMock instead of AsyncMock for update
        from unittest.mock import MagicMock

        mock_progress_bar = MagicMock()
        mock_progress_bar.update = MagicMock()

        # Run the test
        _ = asyncio.run(
            translate_context(
                original=original_dialogues,
                target_language="Spanish",
                progress_bar=mock_progress_bar,
            )
        )

        # Verify progress bar was updated
        self.assertTrue(mock_progress_bar.update.called)

    @patch("llm.base._send_llm_request")
    def test_translate_context_retry_on_error(self, mock_send_llm_request):
        # Setup mock responses for first and second calls
        call_count = 0

        async def mock_generator(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API Error")
            else:
                response = json.dumps(
                    {"context": [{"original": "John", "translated": "John"}]}
                )
                for char in response:
                    yield char

        # Reset the mock for each call to avoid side effects
        mock_send_llm_request.reset_mock()
        mock_send_llm_request.side_effect = mock_generator

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello John", actor=None, style=None)
        ]

        # Run the test
        with patch(
            "asyncio.sleep", new_callable=AsyncMock
        ):  # Mock sleep to speed up test
            asyncio.run(
                translate_context(
                    original=original_dialogues, target_language="Spanish"
                )
            )

        # Verify the mock was called twice (initial failure + retry)
        self.assertEqual(mock_send_llm_request.call_count, 2)

    @patch("llm.base._send_llm_request")
    def test_translate_dialouges_success(self, mock_send_llm_request):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps(
                {"translated": {"1": "Hola", "2": "Mundo", "3": "Prueba"}}
            )
            for char in response:
                yield char

        mock_send_llm_request.return_value = mock_generator()

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None),
            SubtitleDialogue(id="2", content="World", actor=None, style=None),
            SubtitleDialogue(id="3", content="Test", actor=None, style=None),
        ]

        expected = [
            SubtitleDialogue(id="1", content="Hola"),
            SubtitleDialogue(id="2", content="Mundo"),
            SubtitleDialogue(id="3", content="Prueba"),
        ]

        # Run the test
        result = list(
            asyncio.run(
                translate_dialogues(
                    original=original_dialogues, target_language="Spanish"
                )
            )
        )

        # Verify results
        self.assertEqual(result, expected)

        # Verify the mock was called with the right parameters
        mock_send_llm_request.assert_called_once()
        args, kwargs = mock_send_llm_request.call_args
        # Check that Spanish is in one of the instructions
        self.assertTrue(
            any("Spanish" in instruction for instruction in kwargs["instructions"])
        )

    @patch("llm.base._send_llm_request")
    def test_translate_dialouges_with_pretranslate(self, mock_send_llm_request):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps(
                {"translated": {"1": "Hola John", "2": "Bienvenido a Madrid"}}
            )
            for char in response:
                yield char

        mock_send_llm_request.return_value = mock_generator()

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello John", actor=None, style=None),
            SubtitleDialogue(
                id="2", content="Welcome to Madrid", actor=None, style=None
            ),
        ]

        pretranslate_context = [
            PreTranslatedContext(
                original="John", translated="John", description="Name"
            ),
            PreTranslatedContext(
                original="Madrid", translated="Madrid", description="City"
            ),
        ]

        expected = [
            SubtitleDialogue(id="1", content="Hola John"),
            SubtitleDialogue(id="2", content="Bienvenido a Madrid"),
        ]

        # Run the test
        result = list(
            asyncio.run(
                translate_dialogues(
                    original=original_dialogues,
                    target_language="Spanish",
                    pretranslate=pretranslate_context,
                )
            )
        )

        # Verify results
        self.assertEqual(result, expected)

        # Verify pretranslate was passed to the function
        mock_send_llm_request.assert_called_once()
        _, kwargs = mock_send_llm_request.call_args
        pretranslate_arg: PreTranslatedContextSetDTO = kwargs["pretranslate"]
        self.assertEqual(pretranslate_arg.to_contexts(), pretranslate_context)

    @patch("llm.base._send_llm_request")
    def test_translate_dialouges_with_progress_bar(self, mock_send_llm_request):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps({"translated": {"1": "Hola"}})
            for char in response:
                yield char

        mock_send_llm_request.return_value = mock_generator()

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None)
        ]

        # Mock progress bar - use MagicMock instead of AsyncMock for update
        from unittest.mock import MagicMock

        mock_progress_bar = MagicMock()
        mock_progress_bar.update = MagicMock()

        # Run the test
        _ = list(
            asyncio.run(
                translate_dialogues(
                    original=original_dialogues,
                    target_language="Spanish",
                    progress_bar=mock_progress_bar,
                )
            )
        )

        # Verify progress bar was updated
        self.assertTrue(mock_progress_bar.update.called)

    @patch("llm.base._send_llm_request")
    def test_translate_dialouges_retry_on_error(self, mock_send_llm_request):
        # Setup mock responses
        call_count = 0

        async def mock_generator_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API Error")

            response = json.dumps({"translated": {"1": "Hola"}})
            for char in response:
                yield char

        # Reset the mock to avoid side effects from other tests
        mock_send_llm_request.reset_mock()
        mock_send_llm_request.side_effect = mock_generator_with_retry

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None)
        ]
        expected = [
            SubtitleDialogue(id="1", content="Hola"),
        ]

        # Run the test
        with patch(
            "asyncio.sleep", new_callable=AsyncMock
        ):  # Mock sleep to speed up test
            result = list(
                asyncio.run(
                    translate_dialogues(
                        original=original_dialogues, target_language="Spanish"
                    )
                )
            )

        # Verify results
        self.assertEqual(result, expected)

        # Verify the mock was called twice (initial failure + retry)
        self.assertEqual(mock_send_llm_request.call_count, 2)

    @patch("llm.base._send_llm_request")
    def test_translate_dialouges_failed_after_retries_send_llm_request(
        self, mock_send_llm_request
    ):
        # Setup mock response to always fail
        async def mock_generator(*args, **kwargs):
            raise Exception("API Error")

        mock_send_llm_request.return_value = mock_generator()

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None)
        ]

        # Run the test and expect a FailedAfterRetries exception
        with self.assertRaises(FailedAfterRetries):
            asyncio.run(
                translate_dialogues(
                    original=original_dialogues, target_language="Spanish"
                )
            )

    @patch("llm.base._send_llm_request")
    @patch("llm.base._simple_sanity_check")
    def test_translate_dialogues_failed_after_retries_sanity_check(
        self, mock_sanity_check, mock_send_llm_request
    ):
        # Setup mock response
        async def mock_generator(*args, **kwargs):
            response = json.dumps({"translated": {"1": "Hola", "2": "Mundo"}})
            for char in response:
                yield char

        mock_sanity_check.return_value = False
        mock_send_llm_request.return_value = mock_generator()

        # Test data
        original_dialogues = [
            SubtitleDialogue(id="1", content="Hello", actor=None, style=None)
        ]

        with self.assertRaises(FailedAfterRetries):
            asyncio.run(
                translate_dialogues(
                    original=original_dialogues, target_language="Spanish"
                )
            )


if __name__ == "__main__":
    unittest.main()
