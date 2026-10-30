"""Desktop shell of the 2.0.0-alpha (internal notes 3.1, appendix C).

Starts the local service as a child process, reads its port and token from <data dir>/service.json, opens one
pywebview window on http://127.0.0.1:<port>/ and stops the service when the window closes. The shell talks to the
service only over HTTP and imports nothing from par_app (13_ section 4: shell -> HTTP only).
"""

SHELL_TITLE = "PAR 光谱仪专用软件 ASMART-GROW-SPECTRA I"
"""V1.0.x's window title; the window adds the version and ALPHA_NOTICE (S-2, 15_ section 4; equal to
par_app.alpha_info.PRODUCT_TITLE, a test keeps them equal)."""
ALPHA_NOTICE = "V2.0 试用版"
