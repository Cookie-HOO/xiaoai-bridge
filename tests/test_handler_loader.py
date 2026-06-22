from __future__ import annotations

import pytest

from xiaoai_bridge.handler_loader import HandlerLoadError, load_handler, parse_handler_spec


def test_parse_handler_spec_defaults_to_handler() -> None:
    assert parse_handler_spec("./handler.py") == ("./handler.py", "handler")
    assert parse_handler_spec("my_bot.handlers") == ("my_bot.handlers", "handler")


def test_parse_handler_spec_uses_explicit_callable() -> None:
    assert parse_handler_spec("./handler.py:reply") == ("./handler.py", "reply")
    assert parse_handler_spec("my_bot.handlers:reply") == ("my_bot.handlers", "reply")


def test_load_builtin_handler() -> None:
    handler = load_handler("xiaoai_bridge.handler:handler")

    assert callable(handler)


def test_load_file_handler(tmp_path) -> None:
    handler_file = tmp_path / "user_handler.py"
    handler_file.write_text(
        "def handler(question, speaker=None):\n"
        "    return f'answer: {question}'\n",
        encoding="utf-8",
    )

    handler = load_handler(f"{handler_file}:handler")

    assert handler("hello") == "answer: hello"


def test_load_file_handler_with_default_callable(tmp_path) -> None:
    handler_file = tmp_path / "user_handler.py"
    handler_file.write_text(
        "def handler(question, speaker=None):\n"
        "    return question.upper()\n",
        encoding="utf-8",
    )

    handler = load_handler(str(handler_file))

    assert handler("hello") == "HELLO"


def test_load_handler_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(HandlerLoadError, match="does not exist"):
        load_handler(str(tmp_path / "missing.py"))


def test_load_handler_rejects_missing_attribute(tmp_path) -> None:
    handler_file = tmp_path / "user_handler.py"
    handler_file.write_text("def other():\n    return 'x'\n", encoding="utf-8")

    with pytest.raises(HandlerLoadError, match="was not found"):
        load_handler(str(handler_file))


def test_load_handler_rejects_non_callable_attribute(tmp_path) -> None:
    handler_file = tmp_path / "user_handler.py"
    handler_file.write_text("handler = 'not callable'\n", encoding="utf-8")

    with pytest.raises(HandlerLoadError, match="not callable"):
        load_handler(str(handler_file))
