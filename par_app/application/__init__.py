"""Application layer of the ui-v2 local service (stage two, route C; internal notes section 4).

Read use cases over imported history snapshots. It calls par_app.services for every displayed text and reads the
snapshot copies through read-only SQLite connections only. It never opens a V1.0.x database for writing, never uses
ParDatabase (which writes on open) and never talks to a device (tier 0, S-4). import-linter keeps Qt, the UI,
the protocol and the coordinator out of this package.
"""

from ..alpha_info import ALPHA_VERSION

__all__ = ["ALPHA_VERSION", "DEVICE_WRITE_TIER"]
DEVICE_WRITE_TIER = 0
"""Device-write tier (13_ section 2.5, S-4): 0 = read-only. Higher tiers need owner's written approval each."""
