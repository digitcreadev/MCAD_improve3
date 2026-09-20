"""Dependency-free validator for the JSON Schema keywords used by this tree."""

from __future__ import annotations

from typing import Any


class ValidationError(AssertionError):
    pass


def validate(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None) -> None:
    root = schema if root is None else root
    if "$ref" in schema:
        target: Any = root
        for component in schema["$ref"].removeprefix("#/").split("/"):
            target = target[component]
        validate(instance, target, root)
        return
    for subschema in schema.get("allOf", []):
        validate(instance, subschema, root)
    if "oneOf" in schema:
        matches = 0
        for subschema in schema["oneOf"]:
            try:
                validate(instance, subschema, root)
                matches += 1
            except ValidationError:
                pass
        if matches != 1:
            raise ValidationError(f"expected one matching schema, got {matches}")
    if "const" in schema and instance != schema["const"]:
        raise ValidationError("const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError("enum mismatch")

    expected = schema.get("type")
    if expected:
        expected_types = expected if isinstance(expected, list) else [expected]
        predicates = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "boolean": lambda value: isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if not any(predicates[name](instance) for name in expected_types):
            raise ValidationError(f"expected {expected_types}, got {type(instance).__name__}")

    if isinstance(instance, dict):
        missing = set(schema.get("required", [])) - instance.keys()
        if missing:
            raise ValidationError(f"missing required fields: {sorted(missing)}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], root)
            elif schema.get("additionalProperties") is False:
                raise ValidationError(f"unexpected property: {key}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            raise ValidationError("too few items")
        if schema.get("uniqueItems") and len({repr(value) for value in instance}) != len(instance):
            raise ValidationError("items are not unique")
        if "items" in schema:
            for value in instance:
                validate(value, schema["items"], root)
    if isinstance(instance, str) and len(instance) < schema.get("minLength", 0):
        raise ValidationError("string too short")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema.get("minimum", instance):
            raise ValidationError("number below minimum")
