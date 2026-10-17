from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import deepseek_stream


class FakeResponse:
    status = 200

    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def __iter__(self):
        return iter(self.lines)


class DeepSeekStreamTests(unittest.TestCase):
    def test_chat_completion_deltas_reconstruct_answer_and_metadata(self) -> None:
        def event(delta: str, finish=None, usage=None) -> bytes:
            payload = {"model": "deepseek-flash", "choices": [{"delta": {"content": delta},
                                                              "finish_reason": finish}], "usage": usage}
            return f"data: {json.dumps(payload)}\n\n".encode()

        lines = [b": keep-alive\n", event("Hello "), event("world", "stop", {"total_tokens": 9}),
                 b"data: [DONE]\n"]
        received = []
        logs = {}

        class Config:
            temperature = 0.2
            top_p = 0.9
            max_tokens = 100

        with tempfile.TemporaryDirectory() as temp, patch.object(deepseek_stream.urllib.request, "urlopen", return_value=FakeResponse(lines)):
            answer, meta = deepseek_stream.complete(
                "deepseek-flash", "Question", Config(), "run-test", "Instructions", key="test-only",
                url="https://example.invalid", logs=Path(temp),
                dump_json=lambda path, value: logs.__setitem__(path.name, value), on_delta=received.append,
            )
        self.assertEqual(answer, "Hello world")
        self.assertEqual(received, ["Hello ", "world"])
        self.assertEqual(meta["finish_reason"], "stop")
        self.assertEqual(meta["usage"]["total_tokens"], 9)
        self.assertTrue(logs["run-test.request.json"]["stream"])
        self.assertEqual(logs["run-test.response.json"]["choices"][0]["message"]["content"], answer)


if __name__ == "__main__":
    unittest.main()
