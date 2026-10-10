#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quick-ai · 划词快捷键助手
选中任意文本 → 按热键 → 翻译 / 润色 / 总结 / 解释，结果显示在弹窗里
Windows 全局热键，纯标准库，零依赖单文件
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

__version__ = "1.0.0"

CONFIG_PATH = Path.home() / ".quick-ai" / "config.json"
REMOTE_URL = "https://raw.githubusercontent.com/dafeiai918/oneclickrelay-remote/main/remote.json"
FALLBACK_RECOMMEND = {"name": "好同根", "url": "https://haotogen.com/"}

IS_WINDOWS = os.name == "nt"

ACTIONS = {
    "translate": {
        "label": "翻译",
        "system": "你是专业翻译。把用户提供的内容翻译成中文；如果原文已是中文则翻译成英文。"
                  "只输出译文，不要解释、不要加引号。",
    },
    "polish": {
        "label": "润色",
        "system": "你是文字编辑。润色用户提供的文本，使其更通顺专业，不改变原意。只输出润色后的文本。",
    },
    "summary": {
        "label": "总结",
        "system": "你是纪要助手。用 3 条以内的要点总结用户提供的内容，每条不超过 30 字。只输出要点。",
    },
    "explain": {
        "label": "解释",
        "system": "你是老师。用通俗易懂的中文解释用户提供的内容，2-4 句话讲清核心，必要时举例。",
    },
    "reply": {
        "label": "起草回复",
        "system": "你是职场沟通助手。针对用户提供的内容（通常是一段消息或邮件），"
                  "起草一条得体的回复，语气专业友好，只输出回复正文。",
    },
}

DEFAULT_CONFIG = {
    "base_url": "",
    "api_key": "",
    "model": "gpt-4o-mini",
    "hotkeys": {
        "translate": "ctrl+alt+1",
        "polish": "ctrl+alt+2",
        "summary": "ctrl+alt+3",
        "explain": "ctrl+alt+4",
        "reply": "ctrl+alt+5",
    },
    "auto_copy": True,
    "timeout": 60,
}


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; CYAN = "\033[36m"; GRAY = "\033[90m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{C.RESET}"


def enable_ansi() -> None:
    if os.name == "nt":
        os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------- 配置 ----------------

def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                cfg.update(stored)
                if isinstance(stored.get("hotkeys"), dict):
                    cfg["hotkeys"] = {**DEFAULT_CONFIG["hotkeys"], **stored["hotkeys"]}
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass


def normalize_base(url: str) -> str:
    root = url.strip().rstrip("/")
    if not root.endswith("/v1"):
        root += "/v1"
    return root


# ---------------- 剪贴板 ----------------

def read_clipboard() -> str:
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text or ""
    except Exception:
        return ""


def write_clipboard(text: str) -> bool:
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


# ---------------- Windows 按键 ----------------

def _win():
    import ctypes
    return ctypes, ctypes.windll.user32


def parse_hotkey(spec: str) -> tuple[int, int] | None:
    mods = 0
    vk = None
    table = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001,
             "shift": 0x0004, "win": 0x0008}
    for part in spec.lower().replace(" ", "").split("+"):
        if part in table:
            mods |= table[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit():
            vk = 0x70 + int(part[1:]) - 1
        else:
            return None
    if vk is None:
        return None
    return mods | 0x4000, vk  # MOD_NOREPEAT


def send_ctrl_c() -> None:
    if not IS_WINDOWS:
        return
    ctypes, user32 = _win()
    VK_CONTROL, VK_C, KEYUP = 0x11, 0x43, 0x0002
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)


# ---------------- 调用模型 ----------------

def complete(cfg: dict, action: str, text: str) -> str:
    action_cfg = ACTIONS.get(action)
    if not action_cfg:
        raise ValueError(f"未知动作：{action}")
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": action_cfg["system"]},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        normalize_base(cfg["base_url"]) + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg['api_key']}",
                 "Content-Type": "application/json",
                 "User-Agent": f"quick-ai/{__version__}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 60)) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return (data["choices"][0]["message"].get("content") or "").strip()


# ---------------- 弹窗 ----------------

def show_popup(title: str, text: str, auto_copy: bool, error: bool = False) -> None:
    def build():
        import tkinter as tk
        from tkinter import font as tkfont

        root = tk.Tk()
        root.title(f"quick-ai · {title}")
        root.attributes("-topmost", True)
        root.geometry("640x420")

        header = tk.Label(root, text=title, anchor="w",
                          font=tkfont.Font(size=12, weight="bold"),
                          fg="#c0392b" if error else "#2c3e50")
        header.pack(fill="x", padx=12, pady=(10, 4))

        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True, padx=12)
        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")
        box = tk.Text(frame, wrap="word", yscrollcommand=scroll.set,
                      font=("Microsoft YaHei UI", 11), relief="flat", bg="#fbfbfb")
        box.pack(side="left", fill="both", expand=True)
        scroll.config(command=box.yview)
        box.insert("1.0", text)
        box.config(state="disabled")

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=12, pady=8)

        def copy_it():
            write_clipboard(text)
            status.config(text="已复制 ✓")

        def close_it():
            root.destroy()

        tk.Button(bar, text="复制", width=10, command=copy_it).pack(side="left")
        tk.Button(bar, text="关闭", width=10, command=close_it).pack(side="left", padx=6)
        status = tk.Label(bar, text="已自动复制" if auto_copy and not error else "",
                          fg="#27ae60")
        status.pack(side="left", padx=10)

        root.bind("<Escape>", lambda _e: root.destroy())
        root.mainloop()

    thread = threading.Thread(target=build, daemon=True)
    thread.start()
    thread.join()


def handle_hotkey(cfg: dict, action: str) -> None:
    label = ACTIONS[action]["label"]
    print(_c(C.GRAY, f"[{time.strftime('%H:%M:%S')}] 触发 {label}"))
    send_ctrl_c()
    time.sleep(0.25)
    text = read_clipboard().strip()
    if not text:
        show_popup(label, "没有取到选中的文本。\n\n请先选中一段文字，再按热键。", False, error=True)
        return
    try:
        result = complete(cfg, action, text)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        exc.close()
        show_popup(label, f"接口返回 {exc.code}：\n{detail}", False, error=True)
        return
    except Exception as exc:
        show_popup(label, f"请求失败：{type(exc).__name__}\n\n检查 setup 里的地址和密钥。", False, error=True)
        return
    if cfg.get("auto_copy") and result:
        write_clipboard(result)
    show_popup(label, result or "(模型返回空内容)", cfg.get("auto_copy", True))


# ---------------- 命令 ----------------

def cmd_setup(args) -> int:
    cfg = load_config()
    if args.url:
        cfg["base_url"] = args.url
    if args.key:
        cfg["api_key"] = args.key
    if args.model:
        cfg["model"] = args.model
    if args.test:
        try:
            out = complete(cfg, "summary", "这是一段用于测试连通性的文字。")
            print(_c(C.GREEN, f"连通性正常，模型回复：{out[:60]}"))
        except Exception as exc:
            print(_c(C.RED, f"连通失败：{type(exc).__name__}"))
            return 1
    save_config(cfg)
    print("配置已保存")
    print(_c(C.GRAY, f"文件：{CONFIG_PATH}"))
    if cfg["base_url"]:
        print(f"  地址  {cfg['base_url']}")
        print(f"  模型  {cfg['model']}")
        print(f"  密钥  {cfg['api_key'][:6]}****" if cfg["api_key"] else "  密钥  (未设置)")
    return 0


def cmd_once(args) -> int:
    cfg = load_config()
    if not cfg["base_url"] or not cfg["api_key"]:
        print(_c(C.RED, "还没配置。先运行：quick-ai setup -u 地址 -k 密钥"))
        return 1
    text = args.text or read_clipboard()
    if not text.strip():
        print(_c(C.RED, "没有输入文本：用 --text 指定，或先把内容复制到剪贴板"))
        return 1
    try:
        result = complete(cfg, args.action, text.strip())
    except Exception as exc:
        print(_c(C.RED, f"请求失败：{type(exc).__name__}"))
        return 1
    print()
    print(_c(C.GRAY, "─" * 60))
    print(result)
    print(_c(C.GRAY, "─" * 60))
    if args.copy:
        print("已复制到剪贴板" if write_clipboard(result) else "复制失败")
    return 0


def cmd_run(args) -> int:
    cfg = load_config()
    if not cfg["base_url"] or not cfg["api_key"]:
        print(_c(C.RED, "还没配置。先运行：quick-ai setup -u 地址 -k 密钥"))
        return 1
    if not IS_WINDOWS:
        print(_c(C.YELLOW, "全局热键目前只支持 Windows。"))
        print("其他系统可用：quick-ai once --action translate --copy")
        return 1

    ctypes, user32 = _win()
    registered: list[int] = []
    print()
    print(_c(C.GRAY, "═" * 56))
    print(_c(C.BOLD, "  quick-ai · 划词助手已启动"))
    print(_c(C.GRAY, "═" * 56))
    hotkey_map: dict[int, str] = {}
    hid = 1
    for action, spec in cfg["hotkeys"].items():
        parsed = parse_hotkey(spec)
        if not parsed:
            continue
        mods, vk = parsed
        if user32.RegisterHotKey(None, hid, mods, vk):
            hotkey_map[hid] = action
            registered.append(hid)
            print(f"  {spec.upper():<16}→ {ACTIONS[action]['label']}")
        else:
            print(_c(C.YELLOW, f"  {spec.upper():<16}→ 注册失败（可能被占用）"))
        hid += 1
    if not registered:
        print(_c(C.RED, "没有注册成功任何热键"))
        return 1
    print(_c(C.GRAY, "═" * 56))
    print("  用法：选中文字 → 按热键 → 看结果弹窗")
    print("  Ctrl+C 停止")
    print()

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint), ("pt_x", ctypes.c_long),
                    ("pt_y", ctypes.c_long)]

    msg = MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                action = hotkey_map.get(int(msg.wParam or 0))
                if action:
                    handle_hotkey(cfg, action)
    except KeyboardInterrupt:
        pass
    finally:
        for hid_ in registered:
            user32.UnregisterHotKey(None, hid_)
        print("\n已停止")
    return 0


def cmd_actions(args) -> int:
    cfg = load_config()
    for name, meta in ACTIONS.items():
        print(f"  {name:<12}{meta['label']:<10}{cfg['hotkeys'].get(name, '-')}")
    return 0


def fetch_recommend(timeout: float = 5.0) -> dict | None:
    try:
        req = urllib.request.Request(REMOTE_URL, headers={"User-Agent": f"quick-ai/{__version__}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        rec = data.get("recommend")
        if isinstance(rec, dict) and isinstance(rec.get("url"), str):
            return rec
    except Exception:
        pass
    return FALLBACK_RECOMMEND


def main(argv: list[str] | None = None) -> int:
    enable_ansi()
    parser = argparse.ArgumentParser(
        prog="quick-ai", description="划词快捷键助手：选中文字按热键，翻译/润色/总结/解释")
    parser.add_argument("-V", "--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="配置中转站地址与密钥")
    p_setup.add_argument("-u", "--url")
    p_setup.add_argument("-k", "--key")
    p_setup.add_argument("-m", "--model")
    p_setup.add_argument("--test", action="store_true", help="保存前测试连通性")
    p_setup.set_defaults(func=cmd_setup)

    p_once = sub.add_parser("once", help="手动执行一次（不启用热键）")
    p_once.add_argument("-a", "--action", choices=list(ACTIONS), default="translate")
    p_once.add_argument("--text")
    p_once.add_argument("--copy", action="store_true")
    p_once.set_defaults(func=cmd_once)

    sub.add_parser("run", help="启动全局热键监听").set_defaults(func=cmd_run)
    sub.add_parser("actions", help="查看动作与热键").set_defaults(func=cmd_actions)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        rec = fetch_recommend()
        if rec:
            print()
            print(_c(C.CYAN, f"  推荐中转站  {rec.get('name', '')}  {rec.get('url', '')}"))
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
