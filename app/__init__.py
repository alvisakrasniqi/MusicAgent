from pathlib import Path


# Allow imports like `app.main` to resolve to the backend package when the
# process starts from the repository root, as on Render.
_backend_app_dir = Path(__file__).resolve().parent.parent / "backend" / "app"
if _backend_app_dir.is_dir():
    __path__.append(str(_backend_app_dir))
