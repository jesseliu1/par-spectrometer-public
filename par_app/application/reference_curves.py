"""Fixed content of the spectrum charts (API-08): the four reference curves and the wavelength-coloured fill.

The values are par_app.services.spectrum_display's copies of the V1.0.3 SpectrumCanvas rules; this module only
passes them on so that the API layer never reads services itself (import contract "API layer reaches services only
through the application layer").
"""

from __future__ import annotations

from ..services.spectrum_display import ReferenceCurve, ReferenceCurves, reference_curves

__all__ = ["ReferenceCurve", "ReferenceCurves", "reference_curves"]
