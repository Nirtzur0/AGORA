from __future__ import annotations

from dash import dash_table, dcc, html
import dash
import plotly.graph_objects as go

from dash_app.components.theme import status_color
from dash_app.data.loaders import (
    load_objective_metrics_latest,
    load_paper_verification_snapshot,
)


dash.register_page(__name__, path="/outputs", name="Outputs")


def _objective_chart() -> dcc.Graph:
    try:
        payload = load_objective_metrics_latest()
    except FileNotFoundError:
        figure = go.Figure()
        figure.update_layout(title="Objective metrics file missing")
        return dcc.Graph(figure=figure, config={"displayModeBar": False})
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("id") for row in payload.records],
                y=[row.get("pass_rate", 0) for row in payload.records],
                marker_color=[status_color(str(row.get("status"))) for row in payload.records],
            )
        ]
    )
    figure.update_layout(title="Objective Output Quality", yaxis_range=[0, 1], yaxis_title="pass_rate")
    return dcc.Graph(figure=figure, config={"displayModeBar": False})


def _paper_chart() -> dcc.Graph:
    try:
        payload = load_paper_verification_snapshot()
    except FileNotFoundError:
        figure = go.Figure()
        figure.update_layout(title="Paper verification snapshot missing")
        return dcc.Graph(figure=figure, config={"displayModeBar": False})
    row = payload.records[0] if payload.records else {}
    figure = go.Figure(
        data=[
            go.Bar(
                x=["cites_total", "claims_total", "edges_total", "states_total"],
                y=[
                    row.get("cites_total", 0),
                    row.get("claims_total", 0),
                    row.get("edges_total", 0),
                    row.get("states_total", 0),
                ],
                marker_color="#1f7a8c",
            )
        ]
    )
    figure.update_layout(title="Paper Verification Output Snapshot", yaxis_title="count")
    return dcc.Graph(figure=figure, config={"displayModeBar": False})


def _quality_indicator_rows() -> list[dict[str, str]]:
    try:
        objective = load_objective_metrics_latest()
    except FileNotFoundError:
        return [
            {
                "output": "objective_metrics_latest",
                "status": "fail",
                "reason": "Missing required file.",
                "check": "make PYTHON=python3 check-objective-metrics",
            }
        ]
    rowset = []
    for metric in objective.records:
        rowset.append(
            {
                "output": metric.get("id"),
                "status": metric.get("status"),
                "reason": metric.get("summary_line") or "No summary provided.",
                "check": metric.get("command") or "n/a",
            }
        )
    return rowset


def layout() -> html.Div:
    return html.Div(
        [
            html.Section(
                [
                    html.H2("Algorithm and Report Outputs"),
                    html.P(
                        "This page maps output artifacts to correctness and completeness indicators and shows how to verify each signal."
                    ),
                ],
                className="panel",
            ),
            html.Section([_objective_chart()], className="panel"),
            html.Section([_paper_chart()], className="panel"),
            html.Section(
                [
                    html.H3("Correctness and Completeness Indicators"),
                    dash_table.DataTable(
                        columns=[
                            {"name": "output", "id": "output"},
                            {"name": "status", "id": "status"},
                            {"name": "reason", "id": "reason"},
                            {"name": "check", "id": "check"},
                        ],
                        data=_quality_indicator_rows(),
                        page_size=10,
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "maxWidth": 280, "whiteSpace": "normal"},
                    ),
                ],
                className="panel",
            ),
            html.Section(
                [
                    html.H3("How to Verify"),
                    html.Ul(
                        [
                            html.Li("Citation specificity: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/worker/test_citation_checks.py"),
                            html.Li("Authority boundary: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_phase_machine.py tests/integration/core_api/test_drafts.py"),
                            html.Li("Critical e2e: make PYTHON=python3 test-e2e-critical"),
                            html.Li("Observability snapshot: make PYTHON=python3 check-observability-snapshot"),
                            html.Li("Data quality (headless): python3 -m dash_app.data.validation --repo-root . --output /tmp/agora-dash-validation.json"),
                        ]
                    ),
                ],
                className="panel",
            ),
        ]
    )
