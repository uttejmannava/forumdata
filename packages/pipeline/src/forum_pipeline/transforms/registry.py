"""Transform function registry."""

from __future__ import annotations

from typing import Any, Callable

TransformFn = Callable[..., list[dict[str, Any]]]

_REGISTRY: dict[str, TransformFn] = {}


def register(name: str) -> Callable[[TransformFn], TransformFn]:
    """Decorator to register a transform function."""
    def decorator(fn: TransformFn) -> TransformFn:
        _REGISTRY[name] = fn
        return fn
    return decorator


def get_transform(name: str) -> TransformFn | None:
    """Look up a registered transform by name."""
    # Ensure built-in transforms are loaded
    import forum_pipeline.transforms.builtins  # noqa: F401
    return _REGISTRY.get(name)
