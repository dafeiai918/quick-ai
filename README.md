# quick-ai · 划词快捷键助手

**选中任意文字 → 按 Ctrl+Alt+1 → 立刻翻译。** 不用切窗口，不用复制粘贴。

Windows 全局热键 · 纯标准库 · 零依赖 · 单文件

---

## 五个动作

| 热键 | 动作 | 说明 |
|---|---|---|
| `Ctrl+Alt+1` | 翻译 | 中文→英文 / 英文→中文，自动判断 |
| `Ctrl+Alt+2` | 润色 | 让文字更通顺专业 |
| `Ctrl+Alt+3` | 总结 | 3 条以内要点 |
| `Ctrl+Alt+4` | 解释 | 通俗解释，2-4 句 |
| `Ctrl+Alt+5` | 起草回复 | 对着一段消息/邮件写回复 |

结果弹窗显示，**自动复制到剪贴板**，直接 Ctrl+V 就能用。

---

## 快速开始

```bash
# 1. 配置你的中转站（--test 会先测连通性）
python quick_ai.py setup -u https://api.example.com/v1 -k sk-xxxx -m gpt-4o-mini --test

# 2. 启动热键监听（保持窗口开着）
python quick_ai.py run

# 3. 用起来：在任何软件里选中文字，按 Ctrl+Alt+1
```

不想用热键也可以命令行调用：

```bash
python quick_ai.py once --action translate --text "Hello world" --copy
python quick_ai.py once --action summary          # 处理剪贴板里的内容
python quick_ai.py actions                        # 查看动作与热键
```

---

## 使用场景

| 场景 | 操作 |
|---|---|
| 看英文文档 | 选中段落 → `Ctrl+Alt+1` → 粘贴译文 |
| 写邮件 | 写完 → `Ctrl+Alt+2` → 润色后替换 |
| 群里长消息 | 选中 → `Ctrl+Alt+3` → 三行看懂 |
| 看不懂的术语 | 选中 → `Ctrl+Alt+4` |
| 收到难回的消息 | 复制 → `Ctrl+Alt+5` → 拿到草稿 |

---

## 配置

`~/.quick-ai/config.json`：

```json
{
  "base_url": "https://api.example.com/v1",
  "api_key": "sk-xxxx",
  "model": "gpt-4o-mini",
  "hotkeys": {
    "translate": "ctrl+alt+1",
    "polish": "ctrl+alt+2",
    "summary": "ctrl+alt+3",
    "explain": "ctrl+alt+4",
    "reply": "ctrl+alt+5"
  },
  "auto_copy": true,
  "timeout": 60
}
```

热键格式：`ctrl+alt+1`、`ctrl+shift+f5`、`alt+q` 等，直接改文件后重启生效。

---

## 开机自启（可选）

把下面内容存成 `quick-ai.vbs` 放进启动文件夹（`Win+R` → `shell:startup`）：

```vbscript
CreateObject("WScript.Shell").Run "pythonw ""C:\path\to\quick_ai.py"" run", 0, False
```

---

## 平台说明

| 平台 | 全局热键 | 其他功能 |
|---|---|---|
| Windows | ✅ | ✅ |
| macOS / Linux | ❌ | ✅（用 `once` 命令） |

非 Windows 平台可以用系统自带快捷键工具调用：

```bash
python quick_ai.py once --action translate --copy
```

---

## 常见问题

**按了没反应？**
- 热键可能被别的软件占用，改 `config.json` 里的热键后重启
- 确认 `quick-ai run` 窗口还开着

**提示"没有取到选中的文本"？**
- 先选中文字再按热键；某些不支持 Ctrl+C 的界面（如部分终端）会失败

**第一次按有延迟？**
- 首次请求要建连接，之后会快很多

---

## 相关项目

| 项目 | 用途 |
|---|---|
| [prompt-vault](https://github.com/dafeiai918/prompt-vault) | 提示词模板库 |
| [relay-converter](https://github.com/dafeiai918/relay-converter) | 一份配置转 19 种客户端格式 |
| [OneClickRelay](https://github.com/dafeiai918/oneclickrelay) | 一键把中转站写进 60+ 客户端 |

---

## License

MIT
