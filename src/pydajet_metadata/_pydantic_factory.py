"""Фабрика динамических Pydantic-моделей (граница с mypy)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from pydantic import BaseModel, create_model

ModelFieldSpec = tuple[object, object]
CreateModelCallable = Callable[..., type[BaseModel]]


def dynamic_model(
    name: str,
    field_specs: dict[str, ModelFieldSpec],
    *,
    module: str,
) -> type[BaseModel]:
    creator = cast(CreateModelCallable, create_model)
    return creator(name, __module__=module, **field_specs)


ModelT = TypeVar("ModelT", bound=BaseModel)


def response_list(model: type[ModelT]) -> object:
    return list[model]
