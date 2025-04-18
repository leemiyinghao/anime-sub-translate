import unittest
from typing import AsyncIterator, Literal, Sequence, Type, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, ValidationError

# ... (keep existing imports)
from .base_task import (
    IBaseTask,
    LiteLLMChoice,  # Add this import
    LiteLLMDelta,  # Add this import
    LiteLLMMessage,
    LiteLLMStreamResponse,  # Add this import
    TaskRequest,
)
from .error import FailedAfterRetries


# Helper function to create mock stream responses
def create_stream_chunk(content: str) -> LiteLLMStreamResponse:
    return LiteLLMStreamResponse(
        finish_reason=None,
        choices=[LiteLLMChoice(delta=LiteLLMDelta(content=content))],
    )


def create_finish_chunk(
    reason: Literal["stop", "length", "content_filter"],
) -> LiteLLMStreamResponse:
    return LiteLLMStreamResponse(finish_reason=reason, choices=[])


# Mock async iterator
T = TypeVar("T")


async def mock_async_iterator(items: Sequence[T]) -> AsyncIterator[T]:
    for item in items:
        yield item


class MockResponseDTO(BaseModel):
    content: str


class MockTask(IBaseTask[MockResponseDTO]):
    _response_dto: Type[MockResponseDTO] = MockResponseDTO
    _messages: list[LiteLLMMessage]
    _sanity_check_result: bool

    def __init__(
        self, messages: list[LiteLLMMessage], sanity_check_result: bool = True
    ):
        self._messages = messages
        self._sanity_check_result = sanity_check_result

    def messages(self) -> list[LiteLLMMessage]:
        return self._messages

    def sanity_check(self, response: MockResponseDTO) -> bool:
        return self._sanity_check_result

    def char_limit(self) -> int:
        return -1


class TestTaskRequest(unittest.IsolatedAsyncioTestCase):
    # ... (keep existing test_send, test_send_retries, test_send_failed_after_retries)

    @patch("llm.base_task.Speedometer.increment")
    @patch("llm.base_task.CostTracker.add_cost")
    @patch("llm.base_task.completion_cost", return_value=0.01)
    @patch("llm.base_task.get_setting")
    async def test_parse_stream_basic(
        self, mock_setting, mock_cost, mock_add_cost, mock_increment
    ):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", False)  # Ensure no reasoning for this test

        stream_input = [
            create_stream_chunk('{"content": '),
            create_stream_chunk('"hello world"}'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        results = [res async for res in task_request.parse_stream(mock_stream)]

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results,
            [
                MockResponseDTO(content="hello world"),
            ],
        )
        mock_increment.assert_called()
        mock_add_cost.assert_called_once()

    @patch("llm.base_task.Speedometer.increment")
    @patch("llm.base_task.CostTracker.add_cost")
    @patch("llm.base_task.completion_cost", return_value=0.01)
    @patch("llm.base_task.get_setting")
    async def test_parse_stream_with_reasoning(
        self, mock_setting, mock_cost, mock_add_cost, mock_increment
    ):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", True)  # Enable reasoning

        stream_input = [
            create_stream_chunk("Reasoning step 1. "),
            create_stream_chunk("Reasoning step 2. ### Final:"),
            create_stream_chunk('{"content": "final answer"}'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        results = []
        async for res in task_request.parse_stream(mock_stream):
            results.append(res)

        self.assertEqual(len(results), 3)
        self.assertEqual(
            results,
            [
                "Reasoning step 1. ",
                "Reasoning step 2. ",
                MockResponseDTO(content="final answer"),
            ],
        )
        mock_increment.assert_called()
        mock_add_cost.assert_called_once()

    @patch("llm.base_task.Speedometer.increment")
    async def test_parse_stream_sanity_check_fail(self, mock_increment):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        # Configure MockTask to fail sanity check
        task = MockTask(messages, sanity_check_result=False)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", False)

        stream_input = [
            create_stream_chunk('{"content": "bad data"}'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        with self.assertRaisesRegex(Exception, "Invalid response from LLM."):
            _ = [res async for res in task_request.parse_stream(mock_stream)]
        mock_increment.assert_called()

    @patch("llm.base_task.Speedometer.increment")
    async def test_parse_stream_char_limit_exceeded(self, mock_increment):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        # Override char_limit for this test
        task.char_limit = MagicMock(return_value=10)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", False)

        stream_input = [
            create_stream_chunk('{"content": "this content is too long"}'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        with self.assertRaisesRegex(Exception, "Character limit exceeded: 10."):
            _ = [res async for res in task_request.parse_stream(mock_stream)]
        mock_increment.assert_called()  # Should be called before exception

    @patch("llm.base_task.Speedometer.increment")
    async def test_parse_stream_invalid_json(self, mock_increment):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", False)

        stream_input = [
            create_stream_chunk('{"content": "incomplete json'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        # Expecting pydantic's ValidationError or potentially JSONDecodeError
        with self.assertRaises(Exception) as cm:
            _ = [res async for res in task_request.parse_stream(mock_stream)]
        # Check if it's a JSON parsing related error (could be wrapped)
        self.assertTrue(isinstance(cm.exception, (ValidationError, ValueError)))
        mock_increment.assert_called()

    @patch("llm.base_task.Speedometer.increment")
    async def test_parse_stream_empty_delta(self, mock_increment):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)
        setattr(task_request, "_reasoning", False)

        stream_input = [
            LiteLLMStreamResponse(  # Chunk with empty delta content
                finish_reason=None,
                choices=[LiteLLMChoice(delta=LiteLLMDelta(content=""))],
            ),
            create_stream_chunk('{"content": "ok"}'),
        ]
        mock_stream = mock_async_iterator(stream_input)

        results = [res async for res in task_request.parse_stream(mock_stream)]

        mock_increment.assert_called_once_with(
            len('{"content": "ok"}')
        )  # Only called for non-empty delta

    async def test_send(self):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)

        # Patch the _send method to avoid actual API calls
        async def mock_send():
            return MockResponseDTO(content="hello")

        task_request._send = mock_send  # type: ignore
        result = await task_request.send()
        self.assertIsInstance(result, MockResponseDTO)
        self.assertEqual(result.content, "hello")

    @patch("llm.base_task.get_setting")
    async def test_send_retries(self, mock_get_setting):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)
        retry_count = 2

        # Patch the _send method to raise an exception initially, then succeed
        async def mock_send():
            nonlocal retry_count
            if retry_count > 0:
                retry_count -= 1
                raise Exception("Simulated error")
            return MockResponseDTO(content="hello")

        task_request._send = mock_send  # type: ignore

        # Patch get_setting to return a small retry delay and backoff
        class MockSetting:
            llm_retry_times = 3
            llm_retry_delay = 0.01
            llm_retry_backoff = 1

        mock_get_setting.return_value = MockSetting()

        result = await task_request.send()
        self.assertIsInstance(result, MockResponseDTO)
        self.assertEqual(result.content, "hello")
        self.assertEqual(retry_count, 0)

    @patch("llm.base_task.get_setting")
    async def test_send_failed_after_retries(self, mock_get_setting):
        messages = [LiteLLMMessage({"role": "user", "content": "test"})]
        task = MockTask(messages)
        task_request = TaskRequest(task)

        # Patch the _send method to always raise an exception
        async def mock_send():
            raise Exception("Simulated error")

        task_request._send = mock_send  # type: ignore

        # Patch get_setting to return a small retry delay and backoff
        class MockSetting:
            llm_retry_times = 2
            llm_retry_delay = 0.01
            llm_retry_backoff = 1

        mock_get_setting.return_value = MockSetting()

        from llm.error import FailedAfterRetries

        with self.assertRaises(FailedAfterRetries):
            await task_request.send()
