import unittest
from unittest.mock import patch

from subtitle_types import Dialogue, Metadata, TermBank, TermBankItem

from llm.base import refine_context, translate_context, translate_dialogues
from llm.dto import (
    DialogueDTO,
    MetadataDTO,
    SubtitleDeltaDTO,
    SubtitleDTO,
    TermBankDTO,
    TermBankItemDTO,
)


class TestTranslateDialogues(unittest.IsolatedAsyncioTestCase):
    @patch("llm.base.TranslateTask")
    @patch("llm.base.TaskRequest")
    async def test_translate_dialogues(self, mock_task_request, mock_translate_task):
        # Define a mock implementation of the underlying task
        async def _mock_translate_task_send() -> SubtitleDeltaDTO:
            return SubtitleDeltaDTO(
                dialogues={
                    "0": "Translated: Hello",
                    "1": "Translated: World",
                }
            )

        mock_task_request.return_value.send.side_effect = _mock_translate_task_send

        # Prepare test data
        original_dialogues = [
            Dialogue(id="0", content="Hello"),
            Dialogue(id="1", content="World"),
        ]
        target_language = "en"
        pretranslate = TermBank(context={})
        metadata = Metadata(
            title="Test",
        )

        # Call the function
        translated_dialogues = await translate_dialogues(
            original_dialogues, target_language, pretranslate, metadata
        )
        translated_dialogues = list(translated_dialogues)

        # Assert the results
        self.assertEqual(len(translated_dialogues), 2)
        self.assertEqual(translated_dialogues[0].content, "Translated: Hello")
        self.assertEqual(translated_dialogues[1].content, "Translated: World")
        mock_task_request.assert_called_once_with(mock_translate_task.return_value)
        mock_translate_task.assert_called_once_with(
            dialogues=SubtitleDTO(
                dialogues=[
                    DialogueDTO(id="0", content="Hello"),
                    DialogueDTO(id="1", content="World"),
                ]
            ),
            target_language=target_language,
            term_bank=None,
            metadata=MetadataDTO.from_metadata(metadata),
        )
        mock_task_request.return_value.send.assert_called_once()


class TestTranslateContext(unittest.IsolatedAsyncioTestCase):
    @patch("llm.base.CollectTermBankTask")
    @patch("llm.base.TaskRequest")
    async def test_translate_context(
        self, mock_task_request, mock_collect_term_bank_task
    ):
        async def _mock_collect_term_bank_task_send() -> TermBankDTO:
            return TermBankDTO(
                context={"Hello": TermBankItemDTO(translated="Bonjour", description="")}
            )

        mock_task_request.return_value.send.side_effect = (
            _mock_collect_term_bank_task_send
        )

        # Prepare test data
        original_dialogues = [
            Dialogue(id="0", content="Hello World"),
            Dialogue(id="1", content="Hello Again"),
        ]
        target_language = "fr"
        metadata = Metadata(title="Test")
        limit = 100

        # Call the function
        term_bank = await translate_context(
            original_dialogues, target_language, metadata, limit
        )

        # Assert the results
        self.assertIsInstance(term_bank, TermBank)
        self.assertIn("Hello", term_bank.context)
        self.assertEqual(term_bank.context["Hello"].translated, "Bonjour")
        mock_task_request.assert_called_once_with(
            mock_collect_term_bank_task.return_value
        )
        mock_collect_term_bank_task.assert_called_once_with(
            dialogues=SubtitleDTO(
                dialogues=[
                    DialogueDTO(id="0", content="Hello World"),
                    DialogueDTO(id="1", content="Hello Again"),
                ]
            ),
            metadata=MetadataDTO.from_metadata(metadata),
            target_language=target_language,
            char_limit=limit,
        )
        mock_task_request.return_value.send.assert_called_once()


class TestRefineContext(unittest.IsolatedAsyncioTestCase):
    @patch("llm.base.RefineTermBankTask")
    @patch("llm.base.TaskRequest")
    async def test_refine_context(self, mock_task_request, mock_refine_term_bank_task):
        # Define a mock implementation of the underlying task
        async def mock_refine_context_task_send() -> TermBankDTO:
            return TermBankDTO(
                context={
                    "Hello": TermBankItemDTO(
                        translated="Bonjour", description="Greeting"
                    ),
                    "World": TermBankItemDTO(translated="Monde", description="Earth"),
                }
            )

        mock_task_request.return_value.send.side_effect = mock_refine_context_task_send
        # Prepare test data
        target_language = "fr"
        contexts = TermBank(
            context={"Hello": TermBankItem(translated="Bonjour", description="")}
        )
        metadata = Metadata(title="Test")
        limit = 100

        # Call the function
        refined_term_bank = await refine_context(
            target_language, contexts, metadata, limit
        )

        # Assert the results
        self.assertIsInstance(refined_term_bank, TermBank)
        self.assertIn("Hello", refined_term_bank.context)
        self.assertEqual(refined_term_bank.context["Hello"].description, "Greeting")
        mock_task_request.assert_called_once_with(
            mock_refine_term_bank_task.return_value
        )
        mock_refine_term_bank_task.assert_called_once_with(
            term_bank=TermBankDTO(
                context={"Hello": TermBankItemDTO(translated="Bonjour", description="")}
            ),
            metadata=MetadataDTO.from_metadata(metadata),
            target_language=target_language,
            char_limit=limit,
        )
        mock_task_request.return_value.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
