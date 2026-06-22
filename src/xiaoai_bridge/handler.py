from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xiaoai_bridge.mina_client import MiNADevice


async def handler(question: str, speaker: MiNADevice) -> AsyncIterator[str]:
    """处理用户问题。

    question 是用户问小爱的问题。
    speaker 是触发这个问题的小爱音箱，常用字段：
    - speaker.display_name：音箱名称
    - speaker.serial_number：SN
    - speaker.mac：MAC

    本示例用于测试流式效果：每 yield 一段文字，对应小爱音箱会播放一段。
    """
    print(f"用户问题：{question}，来自：{speaker.display_name}", flush=True)
    chunks = [
        f"{speaker.display_name} 收到你的问题。",
        f"你刚才问的是：{question}。",
        "这是来自 xiaoai-bridge 的流式测试回复。",
    ]
    for chunk in chunks:
        yield chunk
        await asyncio.sleep(0.8)
