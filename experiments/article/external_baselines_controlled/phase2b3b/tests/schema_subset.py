"""Small local validator for the JSON Schema vocabulary used by these tests."""

import re


def validate(instance, schema, path="$", root=None):
    root = schema if root is None else root
    if "const" in schema and instance != schema["const"]:
        raise AssertionError(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        raise AssertionError(f"{path}: enum mismatch")
    if "type" in schema:
        choices = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
                  "boolean": lambda x: isinstance(x, bool), "null": lambda x: x is None}
        if not any(checks[k](instance) for k in choices):
            raise AssertionError(f"{path}: wrong type")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0): raise AssertionError(f"{path}: too short")
        if "pattern" in schema and not re.search(schema["pattern"], instance): raise AssertionError(f"{path}: pattern mismatch")
    if isinstance(instance, int) and "minimum" in schema and instance < schema["minimum"]:
        raise AssertionError(f"{path}: below minimum")
    if isinstance(instance, dict):
        missing = set(schema.get("required", [])) - set(instance)
        if missing: raise AssertionError(f"{path}: missing {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(instance) - set(properties):
            raise AssertionError(f"{path}: additional properties")
        for key, value in instance.items():
            child = properties.get(key, schema.get("additionalProperties", {}))
            if isinstance(child, dict): validate(value, child, f"{path}.{key}", root)
    if isinstance(instance, list) and "items" in schema:
        for index, value in enumerate(instance): validate(value, schema["items"], f"{path}[{index}]", root)
    for conditional in schema.get("allOf", []):
        try: validate(instance, conditional["if"], path, root)
        except AssertionError: continue
        validate(instance, conditional["then"], path, root)
