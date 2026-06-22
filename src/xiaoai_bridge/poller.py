from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from xiaoai_bridge.mina_client import MiNAClient, MiNADevice

LOGGER = logging.getLogger(__name__)
ALLOWED_ANSWER_TYPES = {"TTS", "LLM"}


@dataclass(slots=True)
class ConversationRecord:
    question: str
    timestamp: int
    request_id: str

    @property
    def dedupe_key(self) -> str:
        return self.request_id or f"{self.timestamp}:{self.question}"


class ConversationPoller:
    def __init__(self, client: MiNAClient, device: MiNADevice) -> None:
        self.client = client
        self.device = device
        self.last_seen = 0
        self.last_empty_log_at = 0.0
        self.recent_keys: deque[str] = deque(maxlen=200)

    async def initialize(self) -> None:
        records = await self._fetch_records()
        if records:
            self.last_seen = max(record.timestamp for record in records)
        LOGGER.info("Conversation cursor initialized at %s", self.last_seen)

    async def fetch_new_questions(self) -> list[ConversationRecord]:
        records = await self._fetch_records()
        if not records:
            return []

        max_seen = max(record.timestamp for record in records)
        fresh = [record for record in records if record.timestamp > self.last_seen]
        fresh.sort(key=lambda record: record.timestamp)

        questions = []
        for record in fresh:
            if record.dedupe_key in self.recent_keys:
                continue
            self.recent_keys.append(record.dedupe_key)
            questions.append(record)

        if max_seen > self.last_seen:
            self.last_seen = max_seen
        return questions

    async def _fetch_records(self) -> list[ConversationRecord]:
        records = await self._fetch_conversation_records()
        if not records:
            records = await self._fetch_ubus_records()
        return records

    async def _fetch_conversation_records(self) -> list[ConversationRecord]:
        payload = await self.client.get_conversations(self.device, limit=10)
        raw_records = payload.get("records") or []
        return [record for item in raw_records if (record := normalize_record(item))]

    async def _fetch_ubus_records(self) -> list[ConversationRecord]:
        raw_records = await self.client.get_nlp_results(self.device)
        records = [record for item in raw_records if (record := normalize_ubus_record(item))]
        if records:
            LOGGER.info("Using nlp_result_get fallback, got %d records", len(records))
        return records


def normalize_record(raw: Any) -> ConversationRecord | None:
    if not isinstance(raw, dict):
        return None

    question = str(raw.get("query") or "").strip()
    if not question:
        return None

    timestamp = raw.get("time") or raw.get("timestamp") or 0
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return None

    request_id = str(raw.get("requestId") or raw.get("request_id") or "")
    return ConversationRecord(question=question, timestamp=timestamp_int, request_id=request_id)


def normalize_ubus_record(raw: Any) -> ConversationRecord | None:
    if not isinstance(raw, dict):
        return None
    nlp = raw.get("nlp")
    if isinstance(nlp, str):
        try:
            nlp = json.loads(nlp)
        except json.JSONDecodeError:
            return None
    if not isinstance(nlp, dict):
        return None

    meta = nlp.get("meta") if isinstance(nlp.get("meta"), dict) else {}
    response = nlp.get("response") if isinstance(nlp.get("response"), dict) else {}
    answers = response.get("answer") if isinstance(response.get("answer"), list) else []

    question = ""
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        intention = answer.get("intention")
        if isinstance(intention, dict):
            question = str(intention.get("query") or "").strip()
        if question:
            break
    if not question:
        return None

    timestamp = meta.get("timestamp") or raw.get("time") or raw.get("timestamp") or 0
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        timestamp_int = int(time.time() * 1000)
    request_id = str(meta.get("request_id") or raw.get("requestId") or raw.get("request_id") or "")
    return ConversationRecord(question=question, timestamp=timestamp_int, request_id=request_id)


def is_user_question_record(answers: Any) -> bool:
    if not isinstance(answers, list) or len(answers) != 1:
        return False
    first = answers[0]
    if not isinstance(first, dict):
        return False
    answer_type = str(first.get("type") or first.get("answerType") or "").upper()
    return answer_type in ALLOWED_ANSWER_TYPES
