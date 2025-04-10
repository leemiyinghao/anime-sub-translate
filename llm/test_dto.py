import unittest

from .dto import (
    SubtitleDialogueResponseDTO,
    obj_or_json,
)


class TestDTO(unittest.TestCase):
    def test_obj_or_json(self):
        # Test with a string JSON input
        json_string = '{"id": "1", "content": "Hello"}'
        result = obj_or_json(SubtitleDialogueResponseDTO, json_string)
        self.assertIsInstance(result, SubtitleDialogueResponseDTO)
        self.assertEqual(result, SubtitleDialogueResponseDTO(id="1", content="Hello"))

        # Test with an already parsed object
        obj = SubtitleDialogueResponseDTO(id="2", content="World")
        result = obj_or_json(SubtitleDialogueResponseDTO, obj)
        self.assertEqual(result, obj)

        # Test with no-valid JSON input
        json_input = '{"invalid": "json"}'
        with self.assertRaises(ValueError):
            obj_or_json(SubtitleDialogueResponseDTO, json_input)
