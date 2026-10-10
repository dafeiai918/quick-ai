# -*- coding: utf-8 -*-
"""quick-ai 测试：临时配置 + 本地假站点，不发外网请求"""
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import quick_ai as qa  # noqa: E402

SEEN = {}


class _Api(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        SEEN["auth"] = self.headers.get("Authorization")
        SEEN["payload"] = payload
        body = json.dumps({"choices": [{"message": {"content": "翻译结果：你好世界"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class QuickAiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), _Api)
        cls.api_port = cls.api.server_address[1]
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.api.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = qa.CONFIG_PATH
        qa.CONFIG_PATH = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        qa.CONFIG_PATH = self._orig
        self.tmp.cleanup()

    def _setup(self):
        return qa.main(["setup", "-u", f"http://127.0.0.1:{self.api_port}/v1",
                        "-k", "sk-test", "-m", "mock-model"])

    # ---------- 配置 ----------

    def test_normalize_base(self):
        self.assertEqual(qa.normalize_base("https://a.com"), "https://a.com/v1")
        self.assertEqual(qa.normalize_base("https://a.com/v1"), "https://a.com/v1")
        self.assertEqual(qa.normalize_base("https://a.com/v1/"), "https://a.com/v1")

    def test_defaults_when_no_config(self):
        cfg = qa.load_config()
        self.assertEqual(cfg["model"], "gpt-4o-mini")
        self.assertIn("translate", cfg["hotkeys"])

    def test_setup_saves_and_merges_hotkeys(self):
        self.assertEqual(self._setup(), 0)
        cfg = qa.load_config()
        self.assertEqual(cfg["api_key"], "sk-test")
        self.assertEqual(len(cfg["hotkeys"]), 5)

    def test_setup_test_flag(self):
        self.assertEqual(qa.main(["setup", "-u", f"http://127.0.0.1:{self.api_port}/v1",
                                  "-k", "sk-test", "--test"]), 0)

    # ---------- 热键解析 ----------

    def test_parse_hotkey(self):
        self.assertEqual(qa.parse_hotkey("ctrl+alt+1"), (0x0002 | 0x0001 | 0x4000, ord("1")))
        self.assertEqual(qa.parse_hotkey("ctrl+shift+f5"),
                         (0x0002 | 0x0004 | 0x4000, 0x70 + 4))
        self.assertIsNone(qa.parse_hotkey("ctrl+alt"))
        self.assertIsNone(qa.parse_hotkey("随便写的东西"))

    # ---------- 调用 ----------

    def test_complete_sends_auth_and_system_prompt(self):
        self._setup()
        cfg = qa.load_config()
        out = qa.complete(cfg, "translate", "hello world")
        self.assertIn("你好世界", out)
        self.assertEqual(SEEN["auth"], "Bearer sk-test")
        self.assertEqual(SEEN["payload"]["model"], "mock-model")
        self.assertIn("翻译", SEEN["payload"]["messages"][0]["content"])

    def test_complete_unknown_action(self):
        cfg = qa.load_config()
        with self.assertRaises(ValueError):
            qa.complete(cfg, "不存在", "x")

    def test_once_with_text(self):
        self._setup()
        self.assertEqual(qa.main(["once", "--text", "hello", "--action", "translate"]), 0)

    def test_once_without_config(self):
        self.assertEqual(qa.main(["once", "--text", "hello"]), 1)

    def test_once_without_text(self):
        self._setup()
        orig = qa.read_clipboard
        qa.read_clipboard = lambda: ""
        try:
            self.assertEqual(qa.main(["once"]), 1)
        finally:
            qa.read_clipboard = orig

    def test_request_failure_returns_error(self):
        qa.main(["setup", "-u", "http://127.0.0.1:1/v1", "-k", "sk-test"])
        self.assertEqual(qa.main(["once", "--text", "hello"]), 1)

    def test_actions_command(self):
        self.assertEqual(qa.main(["actions"]), 0)

    def test_run_rejects_unconfigured(self):
        rc = qa.main(["run"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
