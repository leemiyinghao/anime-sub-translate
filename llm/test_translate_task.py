import unittest

from parameterized import parameterized

from llm.dto import (
    DialogueDTO,
    MetadataDTO,
    SubtitleDeltaDTO,
    SubtitleDTO,
    TermBankDTO,
    TermBankItemDTO,
)
from llm.translate_task import TranslateTask, _check_equal


class TestCheckEqual(unittest.TestCase):
    def test_check_equal_same_ids(self):
        request = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="hello"),
                DialogueDTO(id="2", content="world"),
            ]
        )
        response = SubtitleDeltaDTO(
            dialogues={"1": "translated hello", "2": "translated world"}
        )
        self.assertTrue(_check_equal(request, response))

    def test_check_equal_different_ids(self):
        request = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="hello"),
                DialogueDTO(id="2", content="world"),
            ]
        )
        response = SubtitleDeltaDTO(
            dialogues={"1": "translated hello", "3": "translated world"}
        )
        self.assertFalse(_check_equal(request, response))

    def test_check_equal_missing_ids(self):
        request = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="hello"),
                DialogueDTO(id="2", content="world"),
            ]
        )
        response = SubtitleDeltaDTO(
            dialogues={
                "1": "translated hello",
            }
        )
        self.assertFalse(_check_equal(request, response))

    def test_check_equal_extra_ids(self):
        request = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="hello"),
            ]
        )
        response = SubtitleDeltaDTO(
            dialogues={"1": "translated hello", "2": "translated world"}
        )
        self.assertFalse(_check_equal(request, response))

    def test_check_equal_empty(self):
        request = SubtitleDTO(dialogues=[])
        response = SubtitleDeltaDTO(dialogues={})
        self.assertTrue(_check_equal(request, response))


class TestTranslateTask(unittest.TestCase):
    @parameterized.expand(
        [
            (None, None),
            (TermBankDTO(context={"some": TermBankItemDTO(translated="term")}), None),
            (None, MetadataDTO(title="test title", characters=[])),
            (
                TermBankDTO(context={"some": TermBankItemDTO(translated="term")}),
                MetadataDTO(title="test title", characters=[]),
            ),
        ],
    )
    def test_context_prompt(self, term_bank, metadata):
        dialogues = SubtitleDTO(dialogues=[DialogueDTO(id="1", content="hello")])
        task = TranslateTask(
            dialogues=dialogues, term_bank=term_bank, metadata=metadata
        )
        self.assertIsInstance(task.context_prompt(), str)

    def test_action_prompt(self):
        dialogues = SubtitleDTO(dialogues=[DialogueDTO(id="1", content="hello")])
        task = TranslateTask(dialogues=dialogues, target_language="Japanese")
        self.assertIsInstance(task.action_prompt(), str)
