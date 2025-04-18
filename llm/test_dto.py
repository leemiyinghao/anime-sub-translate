import unittest

from .dto import (
    DialogueDTO,
    SubtitleDeltaDTO,
    SubtitleDTO,
    obj_or_json,
)


class TestDTO(unittest.TestCase):
    def test_obj_or_json(self):
        # Test with a string JSON input
        json_string = '{"id": "1", "content": "Hello"}'
        result = obj_or_json(DialogueDTO, json_string)
        self.assertIsInstance(result, DialogueDTO)
        self.assertEqual(result, DialogueDTO(id="1", content="Hello"))

        # Test with an already parsed object
        obj = DialogueDTO(id="2", content="World")
        result = obj_or_json(DialogueDTO, obj)
        self.assertEqual(result, obj)

        # Test with no-valid JSON input
        json_input = '{"invalid": "json"}'
        with self.assertRaises(ValueError):
            obj_or_json(DialogueDTO, json_input)


class TestSubtitleDTO(unittest.TestCase):
    def test_subtitle_dto_apply_delta(self):
        original = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="Hello"),
                DialogueDTO(id="2", content="World"),
            ]
        )
        delta = SubtitleDeltaDTO(
            dialogues={
                "1": "Hi",
                "3": "Everyone",
            }
        )
        expected = SubtitleDTO(
            dialogues=[
                DialogueDTO(id="1", content="Hi"),
                DialogueDTO(id="2", content="World"),
            ]
        )
        result = original.apply_delta(delta)
        self.assertEqual(result, expected)
