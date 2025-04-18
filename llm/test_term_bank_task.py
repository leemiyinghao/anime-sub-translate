import unittest

from subtitle_types import Dialogue

from llm.dto import Metadata, MetadataDTO, SubtitleDTO, TermBankDTO, TermBankItemDTO
from llm.term_bank_task import (
    CollectTermBankTask,
    RefineTermBankTask,
    term_bank_sanity_check,
)


class TestTermBankSanityCheck(unittest.TestCase):
    def test_term_bank_sanity_check_valid(self):
        term_bank = TermBankDTO(
            context={
                "term1": TermBankItemDTO(translated="translated1", description="desc1"),
                "term2": TermBankItemDTO(translated="translated2", description="desc2"),
            }
        )
        self.assertTrue(term_bank_sanity_check(term_bank))

    def test_term_bank_sanity_check_invalid_empty_term(self):
        term_bank = TermBankDTO(
            context={"": TermBankItemDTO(translated="translated1", description="desc1")}
        )
        self.assertFalse(term_bank_sanity_check(term_bank))

    def test_term_bank_sanity_check_invalid_empty_translation(self):
        term_bank = TermBankDTO(
            context={"term1": TermBankItemDTO(translated="", description="desc1")}
        )
        self.assertFalse(term_bank_sanity_check(term_bank))

    def test_term_bank_sanity_check_invalid_same_term_and_translation(self):
        term_bank = TermBankDTO(
            context={"term1": TermBankItemDTO(translated="term1", description="desc1")}
        )
        self.assertFalse(term_bank_sanity_check(term_bank))

    def test_term_bank_sanity_check_empty_context(self):
        term_bank = TermBankDTO(context={})
        self.assertTrue(term_bank_sanity_check(term_bank))


class TestCollectTermBankTask(unittest.TestCase):
    def test_collect_term_bank_task_context_prompt(self):
        dialogues = SubtitleDTO.from_subtitle(
            [Dialogue(id="1", content="test dialogue")]
        )
        task = CollectTermBankTask(dialogues=dialogues)
        prompt = task.context_prompt()
        self.assertIn("test dialogue", prompt)

    def test_collect_term_bank_task_action_prompt(self):
        dialogues = SubtitleDTO.from_subtitle(
            [Dialogue(id="1", content="test dialogue")]
        )
        task = CollectTermBankTask(dialogues=dialogues)
        prompt = task.action_prompt()
        self.assertIn("Prefill the translation", prompt)

    def test_collect_term_bank_task_char_limit(self):
        dialogues = SubtitleDTO.from_subtitle(
            [Dialogue(id="1", content="test dialogue")]
        )
        task = CollectTermBankTask(dialogues=dialogues)
        self.assertGreater(task._char_limit, 0)


class TestRefineTermBankTask(unittest.TestCase):
    def test_refine_term_bank_task_context_prompt(self):
        term_bank = TermBankDTO(
            context={
                "term1": TermBankItemDTO(translated="translated1", description="desc1")
            }
        )
        task = RefineTermBankTask(term_bank=term_bank)
        prompt = task.context_prompt()
        self.assertIn("term1", prompt)
        self.assertIn("translated1", prompt)
        self.assertIn("desc1", prompt)

    def test_refine_term_bank_task_action_prompt(self):
        term_bank = TermBankDTO(
            context={
                "term1": TermBankItemDTO(translated="translated1", description="desc1")
            }
        )
        task = RefineTermBankTask(term_bank=term_bank)
        prompt = task.action_prompt()
        self.assertIn("Generate an analysis", prompt)

    def test_refine_term_bank_task_char_limit(self):
        term_bank = TermBankDTO(
            context={
                "term1": TermBankItemDTO(translated="translated1", description="desc1")
            }
        )
        task = RefineTermBankTask(term_bank=term_bank)
        self.assertGreater(task._char_limit, 0)


if __name__ == "__main__":
    unittest.main()
