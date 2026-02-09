from __future__ import annotations

import json

from dash import Input, Output, callback, dash_table, html
import dash

from dash_app.components.filters import status_filter
from dash_app.data.validation import run_validation


dash.register_page(__name__, path="/data-quality", name="Data Quality")


def _rule_rows() -> list[dict]:
    report = run_validation()
    rows = []
    for item in report["results"]:
        rows.append(
            {
                "dataset_id": item["dataset_id"],
                "rule_id": item["rule_id"],
                "severity": item["severity"],
                "status": item["status"],
                "message": item["message"],
                "metrics": json.dumps(item.get("metrics", {}), sort_keys=True),
                "offending_rows": item.get("offending_rows", []),
            }
        )
    return rows


def layout() -> html.Div:
    rows = _rule_rows()
    failed = sum(1 for row in rows if row["status"] == "fail")

    return html.Div(
        [
            html.Section(
                [
                    html.H2("Data Quality Checks"),
                    html.P(
                        f"Rule execution summary: {len(rows) - failed} pass / {failed} fail. "
                        "Select rows below to inspect failing samples and metrics."
                    ),
                    status_filter(),
                ],
                className="panel",
            ),
            html.Section(
                [
                    dash_table.DataTable(
                        id="quality-table",
                        columns=[
                            {"name": "dataset_id", "id": "dataset_id"},
                            {"name": "rule_id", "id": "rule_id"},
                            {"name": "severity", "id": "severity"},
                            {"name": "status", "id": "status"},
                            {"name": "message", "id": "message"},
                            {"name": "metrics", "id": "metrics"},
                        ],
                        data=rows,
                        page_size=12,
                        sort_action="native",
                        filter_action="native",
                        row_selectable="single",
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "maxWidth": 320, "whiteSpace": "normal"},
                    )
                ],
                className="panel",
            ),
            html.Section(
                [
                    html.H3("Failing Sample Rows"),
                    html.Pre(id="quality-offending", className="json-viewer"),
                ],
                className="panel",
            ),
        ]
    )


@callback(
    Output("quality-table", "data"),
    Input("status-filter", "value"),
)
def filter_quality_rows(selected_statuses: list[str] | None):
    statuses = set(selected_statuses or [])
    rows = _rule_rows()
    if not statuses:
        return rows
    return [row for row in rows if row.get("status") in statuses]


@callback(
    Output("quality-offending", "children"),
    Input("quality-table", "derived_virtual_data"),
    Input("quality-table", "derived_virtual_selected_rows"),
)
def show_offending_rows(rows: list[dict] | None, selected_rows: list[int] | None):
    if not rows:
        return "No rows available for the current filter."
    if not selected_rows:
        return "Select a rule row to inspect offending records."

    idx = selected_rows[0]
    if idx >= len(rows):
        return "Selected row is out of range."

    offending = rows[idx].get("offending_rows", [])
    if not offending:
        return "No offending rows for the selected rule."

    return json.dumps(offending, indent=2, sort_keys=True)
