import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from production_engine import engine
from production_engine.cli import main
from production_engine.safety import safe_log

CANARY = "canary-secret-value-123456"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def completion(content, finish="stop"):
    body = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
    return FakeResponse(json.dumps(body).encode())


def env(**extra):
    return mock.patch.dict(os.environ, {"OPENAI_API_KEY": CANARY, **extra}, clear=True)


def call(response=None, side_effect=None):
    with mock.patch.object(
        engine._OPENER, "open", return_value=response, side_effect=side_effect
    ):
        return engine.call_llm("prompt")


class CallLlmErrorTests(unittest.TestCase):
    def test_success(self):
        with env():
            self.assertEqual(call(completion('{"a": 1}')), {"a": 1})

    def test_http_error_never_echoes_response_body(self):
        body = json.dumps(
            {
                "error": {
                    "message": f"Incorrect API key provided: {CANARY}",
                    "code": "invalid_api_key",
                }
            }
        )
        exc = urllib.error.HTTPError(
            "https://x", 401, "Unauthorized", {}, io.BytesIO(body.encode())
        )
        with env(), self.assertRaises(RuntimeError) as ctx:
            call(side_effect=exc)
        message = str(ctx.exception)
        self.assertNotIn(CANARY, message)
        self.assertNotIn("Incorrect API key", message)
        self.assertIn("HTTP 401", message)
        self.assertIn("invalid_api_key", message)

    def test_http_error_with_hostile_or_non_json_body_gives_status_only(self):
        for body in (
            b"<html>\x1b[31m evil",
            json.dumps({"error": {"code": "x" * 500}}).encode(),
            json.dumps({"error": {"code": "bad code\nwith newline"}}).encode(),
        ):
            exc = urllib.error.HTTPError("https://x", 500, "err", {}, io.BytesIO(body))
            with env(), self.assertRaises(RuntimeError) as ctx:
                call(side_effect=exc)
            self.assertEqual(str(ctx.exception), "Model API returned HTTP 500")

    def test_truncated_invalid_and_malformed_responses(self):
        cases = {
            "truncated": completion('{"a": 1', finish="length"),
            "invalid json": completion("not json"),
            "wrong shape": FakeResponse(b'{"choices": []}'),
            "not json": FakeResponse(b"<html>"),
        }
        for name, response in cases.items():
            with env(), self.assertRaises(RuntimeError, msg=name):
                call(response)

    def test_oversize_response_rejected(self):
        with (
            env(),
            mock.patch.object(engine, "MAX_RESPONSE_BYTES", 10),
            self.assertRaises(RuntimeError),
        ):
            call(FakeResponse(b"x" * 11))

    def test_timeout_setting_is_validated(self):
        for value in ("abc", "0", "-5", "601"):
            with (
                env(OPENAI_TIMEOUT_SECONDS=value),
                self.assertRaises(RuntimeError, msg=value),
            ):
                call(completion("{}"))


class LogSafetyTests(unittest.TestCase):
    def test_safe_log_redacts_strips_controls_and_truncates(self):
        with env():
            text = safe_log(f"key {CANARY} \x1b[2J Bearer abcdefghijkl")
        self.assertNotIn(CANARY, text)
        self.assertNotIn("\x1b", text)
        self.assertNotIn("abcdefghijkl", text)
        self.assertTrue(safe_log("x" * 1000).endswith("..."))
        self.assertLessEqual(len(safe_log("x" * 1000)), 503)

    def test_cli_error_output_is_redacted(self):
        err = io.StringIO()
        boom = RuntimeError(f"upstream said {CANARY}\x1b[31m")
        with (
            env(),
            mock.patch("sys.stderr", err),
            mock.patch("production_engine.cli.read_idea", side_effect=boom),
        ):
            code = main(["produce", "--idea", "x"])
        self.assertEqual(code, 1)
        self.assertNotIn(CANARY, err.getvalue())
        self.assertNotIn("\x1b", err.getvalue())


if __name__ == "__main__":
    unittest.main()
