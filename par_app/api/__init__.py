"""Local HTTP service of the ui-v2 line (stage two, route C): FastAPI routes, models, error mapping, access guard.

Depends only on par_app.application and par_app.domain; services are reached through the application
layer (import-linter contracts in pyproject.toml); never on the UI, Qt, the protocol or the coordinator.
Entry point: `python -m par_app.api`.
"""
