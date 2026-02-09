from __future__ import annotations

from dash import dcc, html


def dataset_picker(dataset_ids: list[str], default: str) -> html.Div:
    options = [{"label": dataset_id.replace("_", " ").title(), "value": dataset_id} for dataset_id in dataset_ids]
    return html.Div(
        [
            html.Label("Dataset", htmlFor="dataset-picker", className="filter-label"),
            dcc.Dropdown(
                id="dataset-picker",
                options=options,
                value=default,
                clearable=False,
                className="filter-input",
            ),
        ],
        className="filter-group",
    )


def status_filter(default_values: list[str] | None = None) -> html.Div:
    defaults = default_values or ["pass", "fail"]
    return html.Div(
        [
            html.Label("Statuses", htmlFor="status-filter", className="filter-label"),
            dcc.Checklist(
                id="status-filter",
                options=[
                    {"label": "Pass", "value": "pass"},
                    {"label": "Fail", "value": "fail"},
                    {"label": "Warn", "value": "warn"},
                ],
                value=defaults,
                inline=True,
                className="status-filter",
            ),
        ],
        className="filter-group",
    )
