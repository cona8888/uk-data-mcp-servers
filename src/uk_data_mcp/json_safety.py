"""Finite, complexity-bounded JSON for provider responses and saved workspaces."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from typing import Any

MAX_DEPTH = 64
MAX_NODES = 500_000


def validate_json_tree(value: Any, *, max_depth: int = MAX_DEPTH,
                       max_nodes: int = MAX_NODES) -> None:
    """Check without recursive traversal or a second full copy of a large tree.

    Cycles exceed the depth budget. Shared Python subobjects are permitted, as
    JSON serialization writes each occurrence independently.
    """
    stack: list[tuple[Iterator, int]] = [(iter((value,)), 0)]
    visited = 0
    while stack:
        iterator, depth = stack[-1]
        try:
            item = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        visited += 1
        if depth > max_depth or visited > max_nodes:
            raise ValueError("JSON exceeds its depth or complexity limit.")
        if item is None or isinstance(item, (str, bool, int)):
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite.")
        elif isinstance(item, list):
            stack.append((iter(item), depth + 1))
        elif isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings.")
            stack.append((iter(item.values()), depth + 1))
        else:
            raise ValueError("Expected JSON-compatible values.")


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("JSON number overflows the finite numeric range.")
    return value


def _invalid_constant(token: str) -> None:
    raise ValueError("Non-finite JSON constants are not permitted.")


def loads_json(raw: str | bytes | bytearray, *, max_depth: int = MAX_DEPTH,
               max_nodes: int = MAX_NODES) -> Any:
    """Reject excessive nesting before invoking the recursive stdlib decoder."""
    try:
        text = raw if isinstance(raw, str) else bytes(raw).decode("utf-8-sig")
        depth = 0
        quoted = escaped = False
        for character in text:
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character in "[{":
                depth += 1
                if depth > max_depth:
                    raise ValueError("JSON exceeds its nesting limit.")
            elif character in "]}":
                depth -= 1
        value = json.loads(text, parse_float=_finite_float, parse_constant=_invalid_constant)
        validate_json_tree(value, max_depth=max_depth, max_nodes=max_nodes)
        return value
    except (RecursionError, OverflowError, UnicodeError) as exc:
        raise ValueError("JSON could not be decoded safely.") from exc
