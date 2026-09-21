"""Tiny dependency-free validator for the JSON Schema keywords used here."""


def validate_schema_subset(value, schema, path="$"):
    kind = schema.get("type")
    if kind == "object" and not isinstance(value, dict):
        raise AssertionError(f"{path} must be an object")
    if kind == "array" and not isinstance(value, list):
        raise AssertionError(f"{path} must be an array")
    if "const" in schema and value != schema["const"]:
        raise AssertionError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise AssertionError(f"{path} is not in enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise AssertionError(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(schema.get("properties", {}))
            if extras:
                raise AssertionError(f"{path} has extra keys: {sorted(extras)}")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                validate_schema_subset(value[key], child, f"{path}.{key}")
