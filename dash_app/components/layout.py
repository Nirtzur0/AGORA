from __future__ import annotations

from dash import dcc, html


def _nav_link(label: str, href: str) -> html.A:
    return html.A(label, href=href, className="nav-link")


def app_shell(content: html.Div | dcc.Loading) -> html.Div:
    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.H1("AGORA Data Explorer", className="app-title"),
                            html.P(
                                "Explore artifact provenance, objective metrics, outputs, and data quality checks.",
                                className="app-subtitle",
                            ),
                        ],
                        className="title-block",
                    ),
                    html.Nav(
                        [
                            _nav_link("Overview", "/"),
                            _nav_link("Datasets", "/datasets"),
                            _nav_link("Outputs", "/outputs"),
                            _nav_link("Data Quality", "/data-quality"),
                        ],
                        className="top-nav",
                    ),
                ],
                className="app-header",
            ),
            html.Main(content, className="app-content"),
        ],
        className="app-shell",
    )
