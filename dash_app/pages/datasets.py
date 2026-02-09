from __future__ import annotations

from dash import Input, Output, callback, dash_table, dcc, html
import dash
import plotly.graph_objects as go

from dash_app.components.filters import dataset_picker
from dash_app.data.catalog import dataset_specs
from dash_app.data.loaders import load_catalog_rows, load_dataset, records_to_columns


dash.register_page(__name__, path="/datasets", name="Datasets")


_existing_dataset_ids = [row["dataset_id"] for row in load_catalog_rows() if row["exists"]]
DATASET_IDS = _existing_dataset_ids or [spec.dataset_id for spec in dataset_specs()]


def _chart_for_dataset(dataset_id: str, records: list[dict]) -> go.Figure:
    fig = go.Figure()

    if not records:
        fig.update_layout(title=f"{dataset_id}: no records")
        return fig

    if dataset_id == "artifact_registry":
        counts: dict[str, int] = {}
        for row in records:
            kind = row.get("kind") or "unknown"
            counts[kind] = counts.get(kind, 0) + 1
        fig.add_bar(x=list(counts.keys()), y=list(counts.values()))
        fig.update_layout(title="Artifacts by Kind", yaxis_title="count")
        return fig

    if dataset_id == "objective_metrics_latest":
        fig.add_bar(x=[row.get("id") for row in records], y=[row.get("pass_rate") for row in records])
        fig.update_layout(title="Objective Metric Pass Rates", yaxis_range=[0, 1])
        return fig

    if dataset_id == "objective_metrics_history":
        fig.add_scatter(
            x=[row.get("generated_at") for row in records],
            y=[row.get("overall_pass_rate") for row in records],
            mode="lines+markers",
        )
        fig.update_layout(title="Objective Metrics Pass Rate Trend", yaxis_range=[0, 1], xaxis_title="generated_at")
        return fig

    if dataset_id == "observability_snapshot_latest":
        row = records[0]
        fig.add_bar(
            x=["artifact_coverage_percent", "objective_pass_rate"],
            y=[row.get("artifact_coverage_percent", 0), (row.get("objective_pass_rate", 0) or 0) * 100],
        )
        fig.update_layout(title="Observability Snapshot Signals", yaxis_title="percent", yaxis_range=[0, 100])
        return fig

    if dataset_id == "paper_verification_snapshot":
        row = records[0]
        fig.add_bar(
            x=["cites_total", "claims_total", "edges_total", "states_total"],
            y=[
                row.get("cites_total", 0),
                row.get("claims_total", 0),
                row.get("edges_total", 0),
                row.get("states_total", 0),
            ],
        )
        fig.update_layout(title="Paper Verification Snapshot")
        return fig

    fig.update_layout(title=dataset_id)
    return fig


def layout() -> html.Div:
    return html.Div(
        [
            html.Section(
                [
                    html.H2("Datasets Explorer"),
                    dataset_picker(DATASET_IDS, default=DATASET_IDS[0]),
                ],
                className="panel",
            ),
            html.Section([dcc.Graph(id="dataset-chart")], className="panel"),
            html.Section(
                [
                    dash_table.DataTable(
                        id="dataset-table",
                        page_size=10,
                        sort_action="native",
                        filter_action="native",
                        row_selectable="single",
                        style_table={"overflowX": "auto"},
                        style_cell={"textAlign": "left", "maxWidth": 280, "whiteSpace": "normal"},
                    )
                ],
                className="panel",
            ),
            html.Section(
                [
                    html.H3("Row Drilldown"),
                    html.Pre(id="dataset-drilldown", className="json-viewer"),
                ],
                className="panel",
            ),
        ]
    )


@callback(
    Output("dataset-chart", "figure"),
    Output("dataset-table", "columns"),
    Output("dataset-table", "data"),
    Input("dataset-picker", "value"),
)
def update_dataset_content(dataset_id: str):
    try:
        payload = load_dataset(dataset_id)
    except FileNotFoundError:
        figure = go.Figure()
        figure.update_layout(title=f"{dataset_id}: dataset file is missing")
        return figure, [], []

    columns = [{"name": key, "id": key} for key in records_to_columns(payload.records)]
    figure = _chart_for_dataset(dataset_id, payload.records)
    return figure, columns, payload.records


@callback(
    Output("dataset-drilldown", "children"),
    Input("dataset-table", "derived_virtual_data"),
    Input("dataset-table", "derived_virtual_selected_rows"),
)
def update_drilldown(rows: list[dict] | None, selected_rows: list[int] | None):
    if not rows:
        return "Select a dataset to load rows."
    if not selected_rows:
        return "Select a row to inspect JSON details."

    index = selected_rows[0]
    if index >= len(rows):
        return "Selected row is out of range."

    import json

    return json.dumps(rows[index], indent=2, sort_keys=True)
