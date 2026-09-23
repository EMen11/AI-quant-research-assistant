"""Offline audit of the exact structured-output schema serialized by Anthropic's SDK."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from anthropic import Anthropic, BadRequestError, transform_schema
from pydantic import ValidationError

from ai_quant.trust.models import DraftProposal

_NUMERIC_CONSTRAINTS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
}
_STRING_CONSTRAINTS = {"minLength", "maxLength"}
_ARRAY_CONSTRAINTS = {"maxItems", "uniqueItems"}
_SCHEMA_KEYWORDS = {
    "$defs",
    "$ref",
    "additionalProperties",
    "allOf",
    "anyOf",
    "const",
    "default",
    "description",
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "format",
    "items",
    "maximum",
    "maxItems",
    "maxLength",
    "minimum",
    "minItems",
    "minLength",
    "multipleOf",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "title",
    "type",
    "uniqueItems",
}
_TRANSPORT_KEYWORDS = {
    "$defs",
    "$ref",
    "additionalProperties",
    "allOf",
    "anyOf",
    "description",
    "enum",
    "format",
    "items",
    "minItems",
    "pattern",
    "properties",
    "required",
    "title",
    "type",
}
_UNSUPPORTED_PATTERN = re.compile(r"\(\?[=!<]|\\[1-9]|\\[bB]")
_MAX_OPTIONAL_PROPERTIES = 24
_MAX_UNION_PARAMETERS = 16
_MANIFESTLY_EXCESSIVE_DEPTH = 32


@dataclass(frozen=True)
class SchemaIssue:
    family: str
    path: str


@dataclass(frozen=True)
class SchemaStats:
    root_type: object
    objects: int
    properties: int
    optional_properties: int
    unions: int
    nesting_levels: int
    keywords: frozenset[str]
    patterns: tuple[str, ...]
    additional_properties: tuple[object, ...]


def test_serialized_draft_schema_matches_sdk_transform_and_is_compatible() -> None:
    raw = DraftProposal.model_json_schema()
    transformed = transform_schema(raw)
    serialized, http_calls = _capture_serialized_schema()

    assert http_calls == 1
    assert serialized == transformed
    assert _schema_issues(serialized) == ()
    assert _schema_stats(raw) == SchemaStats(
        root_type="object",
        objects=2,
        properties=8,
        optional_properties=3,
        unions=1,
        nesting_levels=5,
        keywords=frozenset(
            {
                "$defs",
                "$ref",
                "additionalProperties",
                "anyOf",
                "default",
                "description",
                "enum",
                "items",
                "maxItems",
                "maxLength",
                "minItems",
                "minLength",
                "pattern",
                "properties",
                "required",
                "title",
                "type",
            }
        ),
        patterns=(
            "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
            "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
        ),
        additional_properties=(False, False),
    )
    assert _schema_stats(serialized) == SchemaStats(
        root_type="object",
        objects=2,
        properties=8,
        optional_properties=3,
        unions=1,
        nesting_levels=5,
        keywords=frozenset(
            {
                "$defs",
                "$ref",
                "additionalProperties",
                "anyOf",
                "description",
                "enum",
                "items",
                "minItems",
                "properties",
                "required",
                "title",
                "type",
            }
        ),
        patterns=(),
        additional_properties=(False, False),
    )


def test_serialized_transport_model_is_closed_and_has_only_llm_fields() -> None:
    serialized, _ = _capture_serialized_schema()
    claim = serialized["$defs"]["ClaimProposal"]

    assert serialized["additionalProperties"] is False
    assert claim["additionalProperties"] is False
    assert set(serialized["properties"]) == {"summary", "claims", "limitations"}
    assert set(claim["properties"]) == {
        "text_template",
        "claim_type",
        "metric_ids",
        "evidence_ids",
        "uncertainty",
    }


def test_strict_pydantic_validation_remains_after_transport_schema_simplification() -> None:
    serialized, _ = _capture_serialized_schema()
    assert "maxLength" not in _schema_stats(serialized).keywords
    payload = {
        "summary": "x" * 2_001,
        "claims": [
            {
                "text_template": "Allowed structure.",
                "claim_type": "limitation",
                "metric_ids": [],
                "evidence_ids": [],
                "uncertainty": None,
            }
        ],
        "limitations": ["Still requires human review."],
    }

    with pytest.raises(ValidationError):
        DraftProposal.model_validate(payload)

    payload["summary"] = "Valid length."
    payload["unexpected"] = "not allowed"
    with pytest.raises(ValidationError):
        DraftProposal.model_validate(payload)


def _schema_with_optional_properties(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {f"field_{index}": {"type": "string"} for index in range(count)},
        "additionalProperties": False,
    }


def _schema_with_unions(count: int) -> dict[str, Any]:
    properties = {
        f"field_{index}": {"anyOf": [{"type": "string"}, {"type": "null"}]}
        for index in range(count)
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _deep_array_schema(depth: int) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    for _ in range(depth):
        schema = {"type": "array", "items": schema}
    return schema


@pytest.mark.parametrize(
    ("schema", "expected_family"),
    (
        ({"type": "number", "minimum": 0}, "minimum"),
        ({"type": "number", "maximum": 1}, "maximum"),
        ({"type": "number", "exclusiveMinimum": 0}, "exclusiveMinimum"),
        ({"type": "number", "exclusiveMaximum": 1}, "exclusiveMaximum"),
        ({"type": "number", "multipleOf": 2}, "multipleOf"),
        ({"type": "string", "minLength": 1}, "minLength"),
        ({"type": "string", "maxLength": 2}, "maxLength"),
        ({"type": "array", "items": {"type": "string"}, "maxItems": 2}, "maxItems"),
        (
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "uniqueItems",
        ),
        ({"type": "array", "items": {"type": "string"}, "minItems": 2}, "minItems"),
        ({"type": "object", "properties": {}}, "additionalProperties"),
        (
            {"type": "object", "properties": {}, "additionalProperties": True},
            "additionalProperties",
        ),
        ({"type": "string", "pattern": "(?=secret)"}, "unsupported_pattern"),
        ({"type": "string", "pattern": "(?<=secret)x"}, "unsupported_pattern"),
        ({"type": "string", "pattern": r"(secret)\1"}, "unsupported_pattern"),
        ({"type": "string", "pattern": r"\bsecret\b"}, "unsupported_pattern"),
        ({"type": "string", "default": "value"}, "unsupported_keyword"),
        ({"$ref": "https://example.invalid/schema.json"}, "external_ref"),
        ({"type": "string", "enum": [{"complex": "value"}]}, "complex_enum"),
        (
            {
                "$defs": {"item": {"type": "string"}},
                "allOf": [{"$ref": "#/$defs/item"}],
            },
            "allOf_ref",
        ),
        (
            {
                "$defs": {
                    "node": {
                        "type": "object",
                        "properties": {"child": {"$ref": "#/$defs/node"}},
                        "additionalProperties": False,
                    }
                },
                "$ref": "#/$defs/node",
            },
            "recursive_schema",
        ),
        (_schema_with_optional_properties(25), "too_many_optional_properties"),
        (_schema_with_unions(17), "too_many_unions"),
        (_deep_array_schema(33), "excessive_depth"),
    ),
)
def test_schema_audit_detects_each_unsupported_family(
    schema: dict[str, Any],
    expected_family: str,
) -> None:
    assert expected_family in {issue.family for issue in _schema_issues(schema)}


def _capture_serialized_schema() -> tuple[dict[str, Any], int]:
    captured: dict[str, Any] = {}
    http_calls = 0

    def record(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            400,
            request=request,
            json={
                "type": "error",
                "error": {"type": "invalid_request_error", "message": "mocked"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(record)) as http_client:
        client = Anthropic(
            api_key="placeholder",
            max_retries=0,
            http_client=http_client,
        )
        with pytest.raises(BadRequestError):
            client.messages.parse(
                model="claude-sonnet-5",
                max_tokens=1_200,
                system="redacted",
                messages=[{"role": "user", "content": "redacted"}],
                output_format=DraftProposal,
                timeout=15.0,
            )

    schema = captured["body"]["output_config"]["format"]["schema"]
    return schema, http_calls


def _schema_issues(schema: dict[str, Any]) -> tuple[SchemaIssue, ...]:
    issues: list[SchemaIssue] = []
    nodes = tuple(_walk_schema(schema))
    objects = tuple(
        (path, node)
        for path, node in nodes
        if node.get("type") == "object" or "properties" in node
    )
    optional_count = 0
    union_count = 0

    if _contains_recursive_ref(schema):
        issues.append(SchemaIssue("recursive_schema", "$"))

    for path, node in nodes:
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#/"):
            issues.append(SchemaIssue("external_ref", f"{path}.$ref"))
        enum = node.get("enum")
        if isinstance(enum, list) and any(isinstance(value, (dict, list)) for value in enum):
            issues.append(SchemaIssue("complex_enum", f"{path}.enum"))
        for keyword in _NUMERIC_CONSTRAINTS | _STRING_CONSTRAINTS | _ARRAY_CONSTRAINTS:
            if keyword in node:
                issues.append(SchemaIssue(keyword, f"{path}.{keyword}"))
        if "minItems" in node and node["minItems"] not in (0, 1):
            issues.append(SchemaIssue("minItems", f"{path}.minItems"))
        pattern = node.get("pattern")
        if isinstance(pattern, str) and _UNSUPPORTED_PATTERN.search(pattern):
            issues.append(SchemaIssue("unsupported_pattern", f"{path}.pattern"))
        if "allOf" in node and any(
            isinstance(part, dict) and "$ref" in part for part in node["allOf"]
        ):
            issues.append(SchemaIssue("allOf_ref", f"{path}.allOf"))
        for keyword in node.keys() & _SCHEMA_KEYWORDS - _TRANSPORT_KEYWORDS:
            if keyword not in (
                _NUMERIC_CONSTRAINTS
                | _STRING_CONSTRAINTS
                | _ARRAY_CONSTRAINTS
                | {"minItems"}
            ):
                issues.append(SchemaIssue("unsupported_keyword", f"{path}.{keyword}"))
        union_count += sum(
            1 for keyword in ("anyOf", "oneOf") if isinstance(node.get(keyword), list)
        )

    for path, node in objects:
        if node.get("additionalProperties") is not False:
            issues.append(SchemaIssue("additionalProperties", f"{path}.additionalProperties"))
        required = set(node.get("required", []))
        optional_count += sum(name not in required for name in node.get("properties", {}))

    if optional_count > _MAX_OPTIONAL_PROPERTIES:
        issues.append(SchemaIssue("too_many_optional_properties", "$"))
    if union_count > _MAX_UNION_PARAMETERS:
        issues.append(SchemaIssue("too_many_unions", "$"))
    if _structural_depth(schema) > _MANIFESTLY_EXCESSIVE_DEPTH:
        issues.append(SchemaIssue("excessive_depth", "$"))
    return tuple(issues)


def _schema_stats(schema: dict[str, Any]) -> SchemaStats:
    nodes = tuple(_walk_schema(schema))
    objects = tuple(
        node for _, node in nodes if node.get("type") == "object" or "properties" in node
    )
    optional = sum(
        name not in set(node.get("required", []))
        for node in objects
        for name in node.get("properties", {})
    )
    return SchemaStats(
        root_type=schema.get("type"),
        objects=len(objects),
        properties=sum(len(node.get("properties", {})) for node in objects),
        optional_properties=optional,
        unions=sum(
            1
            for _, node in nodes
            for keyword in ("anyOf", "oneOf")
            if isinstance(node.get(keyword), list)
        ),
        nesting_levels=_structural_depth(schema),
        keywords=frozenset(
            keyword for _, node in nodes for keyword in node if keyword in _SCHEMA_KEYWORDS
        ),
        patterns=tuple(node["pattern"] for _, node in nodes if "pattern" in node),
        additional_properties=tuple(
            node.get("additionalProperties", "ABSENT") for node in objects
        ),
    )


def _walk_schema(value: object, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        nodes.append((path, value))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                nodes.extend(_walk_schema(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                nodes.extend(_walk_schema(child, f"{path}[{index}]"))
    return nodes


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    current: object = root
    for component in ref[2:].split("/"):
        if not isinstance(current, dict):
            return None
        current = current.get(component.replace("~1", "/").replace("~0", "~"))
    return current if isinstance(current, dict) else None


def _contains_recursive_ref(schema: dict[str, Any]) -> bool:
    def visit(node: object, active_refs: frozenset[str]) -> bool:
        if isinstance(node, list):
            return any(visit(child, active_refs) for child in node)
        if not isinstance(node, dict):
            return False
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            if ref in active_refs:
                return True
            target = _resolve_ref(schema, ref)
            return target is not None and visit(target, active_refs | {ref})
        return any(
            visit(child, active_refs)
            for key, child in node.items()
            if key != "$defs" and isinstance(child, (dict, list))
        )

    return visit(schema, frozenset())


def _structural_depth(schema: dict[str, Any]) -> int:
    def visit(node: object, depth: int, active_refs: frozenset[str]) -> int:
        if not isinstance(node, dict):
            return depth
        ref = node.get("$ref")
        if isinstance(ref, str):
            if ref in active_refs:
                return depth
            target = _resolve_ref(schema, ref)
            return depth if target is None else visit(target, depth, active_refs | {ref})
        depths = [depth]
        depths.extend(
            visit(child, depth + 1, active_refs)
            for child in node.get("properties", {}).values()
        )
        if isinstance(node.get("items"), dict):
            depths.append(visit(node["items"], depth + 1, active_refs))
        for keyword in ("anyOf", "oneOf", "allOf"):
            depths.extend(
                visit(child, depth + 1, active_refs) for child in node.get(keyword, [])
            )
        return max(depths)

    return visit(schema, 1, frozenset())
