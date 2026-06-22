from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

HandlerFunc = Callable[..., Any]

DEFAULT_HANDLER_NAME = "handler"


class HandlerLoadError(RuntimeError):
    """Raised when a configured handler cannot be loaded."""


def parse_handler_spec(spec: str) -> tuple[str, str]:
    """Split a handler spec into module/file target and callable name."""
    normalized = spec.strip()
    if not normalized:
        msg = "Handler spec is empty"
        raise HandlerLoadError(msg)

    target, separator, attribute = normalized.rpartition(":")
    if not separator:
        return normalized, DEFAULT_HANDLER_NAME
    if not target:
        msg = f"Invalid handler spec {spec!r}: missing module or file path"
        raise HandlerLoadError(msg)
    if not attribute:
        msg = f"Invalid handler spec {spec!r}: missing callable name"
        raise HandlerLoadError(msg)
    return target, attribute


def load_handler(spec: str) -> HandlerFunc:
    """Load a handler callable from a module path or Python file path."""
    target, attribute = parse_handler_spec(spec)
    module = load_file_module(target) if is_file_target(target) else load_import_module(target)
    try:
        handler = getattr(module, attribute)
    except AttributeError as exc:
        msg = f"Handler {attribute!r} was not found in {target!r}"
        raise HandlerLoadError(msg) from exc
    if not callable(handler):
        msg = f"Handler {attribute!r} in {target!r} is not callable"
        raise HandlerLoadError(msg)
    return handler


def is_file_target(target: str) -> bool:
    return target.endswith(".py") or "/" in target or "\\" in target


def load_import_module(module_name: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        msg = f"Failed to import handler module {module_name!r}: {exc}"
        raise HandlerLoadError(msg) from exc


def load_file_module(file_name: str) -> Any:
    path = Path(file_name).expanduser().resolve()
    if not path.exists():
        msg = f"Handler file does not exist: {path}"
        raise HandlerLoadError(msg)
    if not path.is_file():
        msg = f"Handler path is not a file: {path}"
        raise HandlerLoadError(msg)

    module_name = f"_xiaoai_bridge_user_handler_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"Failed to create import spec for handler file: {path}"
        raise HandlerLoadError(msg)

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        msg = f"Failed to load handler file {path}: {exc}"
        raise HandlerLoadError(msg) from exc
    return module
