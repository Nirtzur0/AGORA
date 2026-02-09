from __future__ import annotations

from dash import dcc, html
import dash
import plotly.graph_objects as go

from dash_app.components.theme import status_color
from dash_app.data.loaders import (
    load_catalog_rows,
    load_objective_metrics_latest,
    load_observability_snapshot_latest,
)


dash.register_page(__name__, path="/", name="Overview")


def _summary_cards() -> list[html.Div]:
    try:
        objective = load_objective_metrics_latest()
    except FileNotFoundError:
        objective = None

    try:
        observability = load_observability_snapshot_latest()
    except FileNotFoundError:
        observability = None

    snapshot = observability.records[0] if observability and observability.records else {}

    cards = [
        {
            "label": "Objective Metrics",
            "value": len(objective.records) if objective else 0,
            "status": objective.metadata.get("overall", {}).get("status", "fail") if objective else "fail",
        },
        {
            "label": "Objective Pass Rate",
            "value": objective.metadata.get("overall", {}).get("pass_rate", 0.0) if objective else 0.0,
            "status": objective.metadata.get("overall", {}).get("status", "fail") if objective else "fail",
        },
        {
            "label": "Artifacts Indexed",
            "value": snapshot.get("artifact_count", 0),
            "status": snapshot.get("artifact_status", "fail"),
        },
        {
            "label": "Observability Status",
            "value": snapshot.get("overall_status", "unknown"),
            "status": snapshot.get("overall_status", "fail"),
        },
    ]

    nodes: list[html.Div] = []
    for card in cards:
        value = card["value"]
        if isinstance(value, float):
            value = f"{value:.2f}"
        nodes.append(
            html.Div(
                [
                    html.Div(card["label"], className="metric-label"),
                    html.Div(str(value), className="metric-value"),
                ],
                className="metric-card",
                style={"borderTopColor": status_color(str(card["status"]))},
            )
        )
    return nodes


def _dataset_health_chart() -> dcc.Graph:
    rows = load_catalog_rows()
    labels = [row["name"] for row in rows]
    values = [1 if row["exists"] else 0 for row in rows]
    colors = ["#1b6e3c" if row["exists"] else "#b91c1c" for row in rows]

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                text=["present" if value == 1 else "missing" for value in values],
                textposition="auto",
            )
        ]
    )
    figure.update_layout(
        title="Dataset Availability",
        yaxis=dict(title="Availability", range=[0, 1.2], tickvals=[0, 1], ticktext=["missing", "present"]),
        margin=dict(l=20, r=20, t=50, b=120),
    )
    return dcc.Graph(figure=figure, config={"displayModeBar": False})


def layout() -> html.Div:
    return html.Div(
        [
            html.Section(
                [
                    html.H2("Start Here"),
                    html.P(
                        "Use Datasets to inspect raw tables and drill into rows. "
                        "Use Outputs for algorithm/result health. "
                        "Use Data Quality for rule-by-rule pass/fail diagnostics."
                    ),
                ],
                className="panel",
            ),
            html.Section(_summary_cards(), className="metric-grid"),
            html.Section([html.H2("Dataset Health"), _dataset_health_chart()], className="panel"),
        ]
    )
