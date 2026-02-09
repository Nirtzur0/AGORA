from __future__ import annotations

from pathlib import Path
import sys

from dash import Dash, page_container

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dash_app.components.layout import app_shell

app = Dash(
    __name__,
    use_pages=True,
    pages_folder=str(APP_ROOT / "pages"),
    assets_folder=str(APP_ROOT / "assets"),
    suppress_callback_exceptions=True,
    title="AGORA Data Explorer",
)

app.layout = app_shell(page_container)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
