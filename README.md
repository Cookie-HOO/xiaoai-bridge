<div align="center">

# xiaoai-bridge

**Use XiaoAi speakers as a programmable Python voice entrypoint.**

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776AB">
  <img alt="PyPI" src="https://img.shields.io/badge/PyPI-xiaoai--bridge-blue">
  <img alt="XiaoAi" src="https://img.shields.io/badge/XiaoAi-MiNA-FF6900">
  <img alt="Handler" src="https://img.shields.io/badge/Handler-sync%20%7C%20async%20%7C%20stream-blue">
</p>

[简体中文](README.zh-CN.md) · [Quickstart](#quickstart) · [Write a Handler](#write-a-handler) · [Commands](#commands) · [Troubleshooting](#troubleshooting)

</div>

---

## What it does

`xiaoai-bridge` continuously listens to selected XiaoAi speakers, forwards new user questions to your Python handler, then plays the handler response through the same speaker.

```text
You talk to XiaoAi
  ↓
xiaoai-bridge polls XiaoAi conversation records
  ↓
Your handler(question, speaker) runs in your own project
  ↓
xiaoai-bridge plays text or audio through the matching speaker
```

Use it to:

- Connect XiaoAi speakers to your own LLM or automation logic.
- Write home voice automations in plain Python.
- Share one handler across multiple speakers while still knowing which speaker triggered the request.
- Return text, remote audio URLs, local audio paths, or streaming text chunks.

> [!NOTE]
> This project uses Xiaomi MiNA APIs inspired by [`idootop/migpt-next`](https://github.com/idootop/migpt-next). These APIs are not public stable APIs and may be affected by account security policy, device model, firmware version, region, or upstream changes.
>
> `xiaoai-bridge` appends TTS/audio playback after observing conversation records. It may not intercept or replace XiaoAi's original response. On some devices or scenarios, users may hear XiaoAi's native response first, then the handler response.

## Install

### With uv

Create your own bot project and install `xiaoai-bridge` as a dependency:

```bash
mkdir my-xiaoai-bot
cd my-xiaoai-bot
uv init
uv add xiaoai-bridge
```

### With pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install xiaoai-bridge
```

> [!TIP]
> Keep your `handler.py`, `.env`, and any private automation code in your own project. Do not edit `site-packages/xiaoai_bridge/handler.py` or the package source.

## Quickstart

Create `.env` in your own project:

```env
MI_XIAOMI_ACCOUNT=""
MI_XIAOMI_PASSWORD=""
MI_XIAOMI_USER_ID=""
MI_XIAOMI_PASS_TOKEN=""
MI_SPEAKER_SN=""
MI_SPEAKER_MAC=""
MI_HANDLER="./handler.py:handler"
MI_POLL_INTERVAL_SECONDS="1"
MI_TOKEN_CACHE_PATH=".data/token_cache.json"
MI_PUBLIC_BASE_URL=""
MI_FILE_SERVER_HOST="0.0.0.0"
MI_FILE_SERVER_PORT="8765"
```

Recommended login method is `userId + passToken`:

```env
MI_XIAOMI_USER_ID="your Xiaomi userId"
MI_XIAOMI_PASS_TOKEN="your passToken, including the V1: prefix"
```

Create `handler.py` next to `.env`:

```python
def handler(question: str, speaker):
    print(f"Question: {question}, speaker: {speaker.display_name}", flush=True)
    return f"{speaker.display_name} heard: {question}"
```

Check login:

```bash
xiaoai-check-login
```

Select the XiaoAi speakers to listen to:

```bash
xiaoai-select
```

Start the bridge:

```bash
xiaoai-bridge
```

You can also override the handler from the command line:

```bash
xiaoai-bridge --handler ./handler.py:handler
xiaoai-bridge --handler my_bot.handlers:handler
```

Handler priority:

```text
CLI --handler > MI_HANDLER > built-in demo handler
```

## Get passToken

1. Open `https://account.xiaomi.com/` in a browser and sign in.
2. Open Developer Tools.
3. Find Cookies / Storage for `https://account.xiaomi.com`.
4. Copy:
   - `userId`
   - `passToken`
5. Write them to `.env`:

```env
MI_XIAOMI_USER_ID="..."
MI_XIAOMI_PASS_TOKEN="V1:..."
```

If Chrome does not show `passToken`, try Firefox. Copy the `V1:` prefix as part of `passToken`.

## Select XiaoAi speakers

Run the interactive selector:

```bash
xiaoai-select
```

Keys:

| Key | Action |
|---|---|
| `↑` / `↓` | Move cursor |
| `Space` | Select / deselect |
| `a` | Select all / none |
| `Enter` | Save to `.env` |
| `q` | Cancel |

The selector updates:

```env
MI_SPEAKER_SN="sn1,sn2,..."
MI_SPEAKER_MAC="mac1,mac2,..."
```

## Write a Handler

Create a handler in your own project, for example `handler.py`:

```python
from xiaoai_bridge.mina_client import MiNADevice


def handler(question: str, speaker: MiNADevice) -> str | None:
    print(f"Question: {question}, speaker: {speaker.display_name}", flush=True)
    return f"{speaker.display_name}, you asked: {question}"
```

Configure it with one of these forms:

```env
MI_HANDLER="./handler.py:handler"
MI_HANDLER="/absolute/path/to/handler.py:handler"
MI_HANDLER="my_bot.handlers:handler"
```

If the callable name is omitted, `handler` is used by default:

```env
MI_HANDLER="./handler.py"
```

`speaker` commonly contains:

| Field | Meaning |
|---|---|
| `speaker.display_name` | Speaker name, preferring alias/name |
| `speaker.serial_number` | SN |
| `speaker.mac` | MAC address |
| `speaker.hardware` | Hardware model, for example `LX06` |
| `speaker.device_id` | MiNA device id |
| `speaker.miot_did` | Mi Home did |

### Branch by speaker

```python
def handler(question: str, speaker) -> str | None:
    if speaker.display_name == "Living Room XiaoAi":
        return "This reply is from the living room speaker."
    return f"{speaker.display_name} received it."
```

### Async handler

```python
async def handler(question: str, speaker) -> str | None:
    answer = await your_llm_call(question)
    return answer
```

### Streaming handler

```python
import asyncio


async def handler(question: str, speaker):
    async for chunk in ask_your_llm_stream(question):
        yield chunk


async def ask_your_llm_stream(question: str):
    for chunk in ["First sentence.", "Second sentence.", "Third sentence."]:
        await asyncio.sleep(0.5)
        yield chunk
```

Each non-empty yielded chunk triggers one XiaoAi TTS playback.

> [!TIP]
> Yield sentences or short paragraphs, not tokens or single characters. XiaoAi TTS is not a WebSocket audio stream; tiny chunks cause frequent short playback segments.

### Return a remote audio URL

```python
def handler(question: str, speaker) -> str | None:
    return "https://example.com/reply.mp3"
```

### Return a local audio path

```python
def handler(question: str, speaker) -> str | None:
    return "/Users/example/Music/reply.mp3"
```

XiaoAi speakers cannot read files directly from your computer. `xiaoai-bridge` starts a lightweight HTTP server and maps the file to:

```text
http://<your-lan-ip>:8765/audio/<token>.mp3
```

If the speaker cannot access that address, set:

```env
MI_PUBLIC_BASE_URL="http://your-reachable-host:8765"
```

Or return an audio URL that is already reachable by the speaker.

## Commands

| Command | Purpose |
|---|---|
| `xiaoai-bridge` | Start the bridge and listen to selected speakers |
| `xiaoai-bridge --handler ./handler.py:handler` | Start with a specific handler |
| `xiaoai-select` | Interactively select one or more XiaoAi speakers |
| `xiaoai-check-login` | Check Xiaomi login, device list, and selected speakers |
| `xiaoai-test-speak` | Play default test TTS |
| `xiaoai-test-speak "hello"` | Play custom test TTS |

### Source checkout commands

If you are developing this repository itself, use `uv run`:

```bash
uv sync --dev
uv run xiaoai-bridge --handler ./handler.py:handler
uv run ruff check .
uv run pytest
```

## Token expiration

Normally, if cached `serviceToken` expires, the program tries to refresh it with `passToken` from `.env`.

If `passToken` is also invalid, you may see:

- XiaoAi no longer plays your configured response.
- Console errors such as `401`, `XiaomiAuthError`, or `login failed`.
- `xiaoai-check-login` fails.

Recovery:

```bash
# 1. Get a fresh userId / passToken from browser cookies and update .env

# 2. Delete old serviceToken cache
rm -f .data/token_cache.json

# 3. Check login
xiaoai-check-login

# 4. Restart the bridge
xiaoai-bridge
```

## Runtime behavior

On startup, the program:

1. Reads `.env`.
2. Loads the configured handler from `MI_HANDLER` or `--handler`.
3. Uses Xiaomi login state to obtain a MiNA `serviceToken`.
4. Lists devices and matches selected speakers.
5. Initializes conversation cursors without replaying old records.
6. Polls new conversations every `MI_POLL_INTERVAL_SECONDS`.
7. Calls `handler(question, speaker)` for each new question.
8. Plays TTS or audio based on the handler result.

## Troubleshooting

### No sound

Check login first:

```bash
xiaoai-check-login
```

Then test TTS:

```bash
xiaoai-test-speak "test sound"
```

If the command succeeds but there is no sound, check:

- The selected speaker is the one you are testing.
- The speaker is online and not in an abnormal playback state.
- The speaker volume is not zero.

### Handler cannot be loaded

Check `MI_HANDLER`:

```env
MI_HANDLER="./handler.py:handler"
```

Make sure:

- the file exists relative to the directory where you run `xiaoai-bridge`;
- the callable exists and is named `handler` or explicitly named after `:`;
- for `module:callable`, the module is importable in the current environment.

### No user questions printed

Confirm:

1. `xiaoai-select` selected the correct device.
2. You asked the selected speaker a question that produces a normal answer, not only the wake word.
3. The bridge is running:

```bash
xiaoai-bridge
```

### Login failed

Prefer passToken login. Frequent automatic account/password login may trigger Xiaomi risk control.

If login fails:

```bash
rm -f .data/token_cache.json
xiaoai-check-login
```

If it still fails, refresh `MI_XIAOMI_USER_ID` and `MI_XIAOMI_PASS_TOKEN`.

## Current boundaries

- Only MiNA-related capabilities are implemented; full MIoT RC4 protocol support is not included.
- Only new questions after startup are processed; old records are not replayed.
- Streaming text is segmented TTS playback, not true audio streaming.
- Local audio playback depends on network reachability. If the speaker cannot access the generated URL, set `MI_PUBLIC_BASE_URL` or return a remote URL.
- Xiaomi APIs may change with time, region, account security policy, or device firmware.

## Security and privacy

- Do not commit `.env`, `.data/token_cache.json`, `passToken`, or `serviceToken` to a public repository.
- `passToken` is a login credential. Refresh it if it expires or leaks.
- Keep `handler.py` private if it contains personal automation logic, keys, or local service URLs.
