"""Application services: pure logic extracted from par_app/ui.py (R-8-1 stage one, behaviour-preserving).

Services never import Qt, matplotlib, sqlite3 or par_app.ui (import-linter contract in pyproject.toml), so the
UI only renders what they return and forwards user actions (R-1-1, R-1-5).
"""
