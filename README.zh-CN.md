<div align="center">

# xiaoai-bridge

**把小爱音箱变成可编程的 Python 语音入口。**

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776AB">
  <img alt="PyPI" src="https://img.shields.io/badge/PyPI-xiaoai--bridge-blue">
  <img alt="XiaoAi" src="https://img.shields.io/badge/XiaoAi-MiNA-FF6900">
  <img alt="Handler" src="https://img.shields.io/badge/Handler-sync%20%7C%20async%20%7C%20stream-blue">
</p>

[English](README.md) · [快速开始](#快速开始) · [编写-handler](#编写-handler) · [命令参考](#命令参考) · [故障排查](#故障排查)

</div>

---

## 这个项目做什么

`xiaoai-bridge` 会持续监听你选择的小爱音箱，把新的用户问题转发给你自己项目里的 Python handler，然后让对应音箱播放 handler 的返回内容。

```text
你对小爱说话
  ↓
xiaoai-bridge 轮询小爱对话记录
  ↓
运行你自己项目里的 handler(question, speaker)
  ↓
根据 handler 返回结果，让对应小爱音箱播放文字或音频
```

适合这些场景：

- 把小爱音箱接到自己的大模型。
- 用 Python 快速实现家庭语音自动化。
- 多台小爱音箱共用一套逻辑，并在 `handler` 里区分来源设备。
- 让 handler 返回文字、远程 mp3 URL、本地 mp3 路径，或流式文本。

> [!NOTE]
> 本项目参考 [`idootop/migpt-next`](https://github.com/idootop/migpt-next) 的 MiNA 调用方式实现。小米相关接口不是公开稳定 API，可能受账号安全策略、设备型号、固件版本、地区和接口调整影响。
>
> `xiaoai-bridge` 通过监听对话记录并向音箱追加 TTS / 音频播放来实现桥接，不一定能拦截或替换小爱音箱原本的回复。部分设备或场景下，可能会先听到小爱原生回复，再听到 handler 返回的内容。

## 安装

### 使用 uv

创建你自己的机器人项目，并把 `xiaoai-bridge` 作为依赖安装：

```bash
mkdir my-xiaoai-bot
cd my-xiaoai-bot
uv init
uv add xiaoai-bridge
xiaoai-init
```

### 使用 pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install xiaoai-bridge
```

> [!TIP]
> 请把 `handler.py`、`.env` 和你的私有自动化代码放在自己的项目目录里。不要修改 `site-packages/xiaoai_bridge/handler.py`，也不要修改包内源码。

## 快速开始

`xiaoai-init` 会在当前目录创建 `.env`、`handler.py` 和一个简单的 `.gitignore`。如果文件已存在，默认跳过；需要覆盖时使用 `--force`。

在 `.env` 中填写小米登录信息：

```env
MI_XIAOMI_USER_ID="你的小米 userId"
MI_XIAOMI_PASS_TOKEN="你的 passToken，包含 V1: 前缀"
```

创建或编辑 `.env` 同级的 `handler.py`：

```python
def handler(question: str, speaker):
    print(f"用户问题：{question}，来自：{speaker.display_name}", flush=True)
    return f"{speaker.display_name} 收到：{question}"
```

检查登录态：

```bash
xiaoai-check-login
```

选择要监听的小爱音箱：

```bash
xiaoai-select
```

启动桥接服务：

```bash
xiaoai-bridge
```

也可以通过命令行临时指定 handler：

```bash
xiaoai-bridge --handler ./handler.py:handler
xiaoai-bridge --handler my_bot.handlers:handler
```

Handler 优先级：

```text
CLI --handler > MI_HANDLER > 包内置示例 handler
```

## 获取 passToken

1. 浏览器打开 `https://account.xiaomi.com/` 并登录。
2. 打开开发者工具。
3. 找到 `Cookies` / `存储` 中的 `https://account.xiaomi.com`。
4. 复制：
   - `userId`
   - `passToken`
5. 写入 `.env`：

```env
MI_XIAOMI_USER_ID="..."
MI_XIAOMI_PASS_TOKEN="V1:..."
```

如果 Chrome 看不到 `passToken`，可以尝试 Firefox。`passToken` 前面的 `V1:` 要一起复制。

## 选择要监听的小爱音箱

运行交互式选择器：

```bash
xiaoai-select
```

操作方式：

| 按键 | 作用 |
|---|---|
| `↑` / `↓` | 移动光标 |
| `空格` | 选择 / 取消选择 |
| `a` | 全选 / 全不选 |
| `Enter` | 保存到 `.env` |
| `q` | 取消 |

保存后会更新：

```env
MI_SPEAKER_SN="sn1,sn2,..."
MI_SPEAKER_MAC="mac1,mac2,..."
```

## 编写 Handler

在你自己的项目中创建 handler，例如 `handler.py`：

```python
from xiaoai_bridge.mina_client import MiNADevice


def handler(question: str, speaker: MiNADevice) -> str | None:
    print(f"用户问题：{question}，来自：{speaker.display_name}", flush=True)
    return f"{speaker.display_name}，你刚才问的是：{question}"
```

可用以下形式配置：

```env
MI_HANDLER="./handler.py:handler"
MI_HANDLER="/absolute/path/to/handler.py:handler"
MI_HANDLER="my_bot.handlers:handler"
```

如果省略 callable 名称，默认使用 `handler`：

```env
MI_HANDLER="./handler.py"
```

`speaker` 常用字段：

| 字段 | 含义 |
|---|---|
| `speaker.display_name` | 音箱名称，优先 alias/name |
| `speaker.serial_number` | SN |
| `speaker.mac` | MAC 地址 |
| `speaker.hardware` | 硬件型号，例如 `LX06` |
| `speaker.device_id` | MiNA device id |
| `speaker.miot_did` | 米家 did |

### 根据来源音箱区分逻辑

```python
def handler(question: str, speaker) -> str | None:
    if speaker.display_name == "客厅小爱":
        return "这是客厅小爱的回复。"
    return f"{speaker.display_name} 收到。"
```

### async handler

```python
async def handler(question: str, speaker) -> str | None:
    answer = await your_llm_call(question)
    return answer
```

### 流式 handler

```python
import asyncio


async def handler(question: str, speaker):
    async for chunk in ask_your_llm_stream(question):
        yield chunk


async def ask_your_llm_stream(question: str):
    for chunk in ["第一段回复。", "第二段回复。", "第三段回复。"]:
        await asyncio.sleep(0.5)
        yield chunk
```

流式模式下，每 `yield` 一段非空文字，程序会立即调用一次小爱 TTS 播放。

> [!TIP]
> 建议按句子或短段落 `yield`，不要按 token / 单字 `yield`。小爱 TTS 不是 WebSocket 音频流，过小的 chunk 会导致频繁播放短片段，体验不好。

### 返回远程 mp3 URL

```python
def handler(question: str, speaker) -> str | None:
    return "https://example.com/reply.mp3"
```

### 返回本地 mp3 路径

```python
def handler(question: str, speaker) -> str | None:
    return "/Users/example/Music/reply.mp3"
```

小爱音箱不能直接读取你电脑上的本地文件。程序会启动一个轻量 HTTP 服务，把本地文件映射为：

```text
http://<你的局域网IP>:8765/audio/<token>.mp3
```

如果小爱音箱访问不到该地址，请设置：

```env
MI_PUBLIC_BASE_URL="http://你的可访问地址:8765"
```

或直接返回公网 / 局域网可访问的音频 URL。

## 命令参考

| 命令 | 作用 |
|---|---|
| `xiaoai-init` | 在用户项目中创建 `.env`、`handler.py` 和 `.gitignore` |
| `xiaoai-bridge` | 启动主程序，监听已选择的小爱音箱 |
| `xiaoai-bridge --handler ./handler.py:handler` | 使用指定 handler 启动 |
| `xiaoai-select` | 交互式选择要监听的小爱音箱，可多选 |
| `xiaoai-check-login` | 检查小米登录态、设备列表和当前监听设备 |
| `xiaoai-test-speak` | 播放默认测试语音 |
| `xiaoai-test-speak "你好"` | 播放自定义测试语音 |

### 源码开发命令

如果你是在开发本仓库本身，使用 `uv run`：

```bash
uv sync --dev
uv run xiaoai-bridge --handler ./handler.py:handler
uv run ruff check .
uv run pytest
```

## Token 过期处理

正常情况下，如果缓存的 `serviceToken` 过期，程序会尝试用 `.env` 里的 `passToken` 自动刷新。

如果 `passToken` 也失效，你可能会看到：

- 小爱不再回复你设定的内容。
- 控制台出现 `401`、`XiaomiAuthError`、`login failed` 等错误。
- `xiaoai-check-login` 检查失败。

快速恢复流程：

```bash
# 1. 重新从浏览器 Cookie 获取 userId / passToken，并更新 .env

# 2. 删除旧 serviceToken 缓存
rm -f .data/token_cache.json

# 3. 检查登录态
xiaoai-check-login

# 4. 检查通过后重启主程序
xiaoai-bridge
```

## 运行时行为

启动后程序会：

1. 读取 `.env`。
2. 从 `MI_HANDLER` 或 `--handler` 加载 handler。
3. 使用小米登录态获取 MiNA `serviceToken`。
4. 拉取设备列表并匹配 `.env` 中选择的小爱音箱。
5. 为每台音箱初始化对话游标，不回放历史问题。
6. 按 `MI_POLL_INTERVAL_SECONDS` 轮询新对话。
7. 发现新问题后调用 `handler(question, speaker)`。
8. 根据 handler 返回值播放 TTS 或音频。

## 故障排查

### 没有声音

先检查登录态：

```bash
xiaoai-check-login
```

再测试 TTS：

```bash
xiaoai-test-speak "测试声音"
```

如果命令成功但没声音，确认：

- 选择的是正在测试的那台音箱。
- 音箱在线且没有处于异常播放状态。
- 音箱音量不为 0。

### Handler 无法加载

检查 `MI_HANDLER`：

```env
MI_HANDLER="./handler.py:handler"
```

确认：

- 文件路径相对于运行 `xiaoai-bridge` 的目录存在；
- callable 存在，名称为 `handler`，或在 `:` 后显式指定；
- 如果使用 `module:callable`，该 module 在当前 Python 环境中可以 import。

### 没有打印用户问题

确认：

1. `xiaoai-select` 选择了正确设备。
2. 你对选中的音箱说了会产生正常回答的问题，而不是只说唤醒词。
3. 主程序正在运行：

```bash
xiaoai-bridge
```

### 登录失败

优先使用 passToken，不建议频繁用账号密码自动登录，因为容易触发小米风控。

如果失败：

```bash
rm -f .data/token_cache.json
xiaoai-check-login
```

仍失败则重新获取 `MI_XIAOMI_USER_ID` 和 `MI_XIAOMI_PASS_TOKEN`。

## 当前边界

- 只实现 MiNA 相关能力，不实现完整 MIoT RC4 协议。
- 只处理启动后的新问题，不回放历史记录。
- 流式文本是“分段多次 TTS”，不是真正的音频流。
- 本地音频播放依赖网络可达性；如果音箱访问不到程序生成的 URL，需要配置 `MI_PUBLIC_BASE_URL` 或返回远程 URL。
- 小米接口可能随时间、地区、账号安全策略或设备固件变化。

## 安全与隐私

- 不要把 `.env`、`.data/token_cache.json`、`passToken`、`serviceToken` 提交到公开仓库。
- `passToken` 等同于登录凭据，过期或泄露后应重新登录刷新。
- 如果 `handler.py` 里包含个人自动化逻辑、密钥或本地服务地址，请保持私有。
