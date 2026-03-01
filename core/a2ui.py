"""
A2UI helpers - Build A2UI messages (surfaceUpdate, dataModelUpdate, beginRendering).
Skills produce these; frontend renders. No transformation in main agent.
"""

from typing import Any


def _list_to_value_map(arr: list[Any]) -> list[dict]:
    """Convert list to valueMap (numeric keys)."""
    out: list[dict] = []
    for i, v in enumerate(arr):
        if isinstance(v, dict):
            out.append({"key": str(i), "valueMap": _to_value_map(v)})
        elif isinstance(v, (list, tuple)):
            out.append({"key": str(i), "valueMap": _list_to_value_map(list(v))})
        elif isinstance(v, (int, float)):
            out.append({"key": str(i), "valueNumber": v})
        else:
            out.append({"key": str(i), "valueString": str(v)})
    return out


def _to_value_map(obj: dict[str, Any]) -> list[dict]:
    """Convert dict to A2UI valueMap adjacency list."""
    out: list[dict] = []
    for k, v in obj.items():
        if v is None:
            out.append({"key": k, "valueString": ""})
        elif isinstance(v, bool):
            out.append({"key": k, "valueBoolean": v})
        elif isinstance(v, (int, float)):
            out.append({"key": k, "valueNumber": v})
        elif isinstance(v, str):
            out.append({"key": k, "valueString": v})
        elif isinstance(v, (list, tuple)):
            out.append({"key": k, "valueMap": _list_to_value_map(list(v))})
        elif isinstance(v, dict):
            out.append({"key": k, "valueMap": _to_value_map(v)})
        else:
            out.append({"key": k, "valueString": str(v)})
    return out


def build_diagnose_a2ui(
    surface_id: str,
    summary: str,
    charts: list[dict[str, Any]],
) -> list[dict]:
    """
    Build A2UI messages for diagnose output.
    Uses List + template; each item is a Chart (custom component). dataModelUpdate for charts.
    """
    if not charts:
        return []

    components = [
        {
            "id": "root-column",
            "component": {
                "Column": {
                    "children": {"explicitList": ["summary-text", "charts-list"]},
                },
            },
        },
        {
            "id": "summary-text",
            "component": {"Text": {"text": {"literalString": summary}, "usageHint": "body"}},
        },
        {
            "id": "charts-list",
            "component": {
                "Column": {
                    "children": {
                        "template": {"dataBinding": "/charts", "componentId": "chart-card"},
                    },
                },
            },
        },
        {
            "id": "chart-card",
            "component": {
                "Card": {"child": "chart-inner"},
            },
        },
        {
            "id": "chart-inner",
            "component": {
                "Chart": {
                    "kind": {"path": "/kind"},
                    "labels": {"path": "/labels"},
                    "values": {"path": "/values"},
                    "chartType": {"path": "/chart_type"},
                    "x": {"path": "/x"},
                    "y": {"path": "/y"},
                },
            },
        },
    ]

    chart_items: list[dict] = []
    for c in charts:
        item: dict[str, Any] = {"kind": c.get("kind", "chart"), "chart_type": c.get("chart_type", "bar")}
        if "labels" in c:
            item["labels"] = c["labels"]
        if "values" in c:
            item["values"] = c["values"]
        if "x" in c:
            item["x"] = c["x"]
        if "y" in c:
            item["y"] = c["y"]
        chart_items.append(item)

    charts_value_map = [{"key": str(i), "valueMap": _to_value_map(item)} for i, item in enumerate(chart_items)]
    contents = [{"key": "charts", "valueMap": charts_value_map}]

    return [
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
        {"dataModelUpdate": {"surfaceId": surface_id, "contents": contents}},
        {"beginRendering": {"surfaceId": surface_id, "root": "root-column"}},
    ]
