"""Objects one service instance shares between requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..application import ALPHA_VERSION
from ..application.acquisition import AcquisitionService
from ..application.acquisition_export import AcquisitionExports
from ..application.diagnostics_bundle import DiagnosticsBundles
from ..application.dli import DliQueries
from ..application.events import EventHub
from ..application.history import HistoryQueries
from ..application.maintenance import MaintenanceService
from ..application.maintenance_log import MaintenanceLogQueries
from ..application.operations import OperationQueries
from ..application.overview import OverviewQueries
from ..application.own_devices import OwnDevices
from ..application.paths import AlphaPaths
from ..application.settings import SettingsQueries
from ..application.snapshots import SnapshotStore
from ..application.timefmt import beijing_iso
from ..domain.clock import Clock


@dataclass
class ServiceContext:
    paths: AlphaPaths
    clock: Clock
    build_commit: str | None = None
    version: str = ALPHA_VERSION
    snapshots: SnapshotStore = field(init=False)
    """Imported snapshots: no page shows them any more (issue #82); listed in diagnostics until #83 removes them."""
    devices: OwnDevices = field(init=False)
    history: HistoryQueries = field(init=False)
    dli: DliQueries = field(init=False)
    operations: OperationQueries = field(init=False)
    settings: SettingsQueries = field(init=False)
    overview: OverviewQueries = field(init=False)
    acquisition_export: AcquisitionExports = field(init=False)
    events: EventHub = field(init=False)
    acquisition: AcquisitionService = field(init=False)
    maintenance: MaintenanceService = field(init=False)
    maintenance_log: MaintenanceLogQueries = field(init=False)
    diagnostics: DiagnosticsBundles = field(init=False)
    started_at: str = field(init=False)

    def __post_init__(self) -> None:
        self.snapshots = SnapshotStore(self.paths, self.clock)
        self.events = EventHub()
        self.acquisition = AcquisitionService(self.paths, self.clock, self.events)
        self.devices = OwnDevices(self.acquisition)
        self.history = HistoryQueries(self.devices)
        self.dli = DliQueries(self.devices, self.clock)
        self.operations = OperationQueries(self.devices, self.clock, self.paths)
        self.settings = SettingsQueries(self.devices)
        self.overview = OverviewQueries(self.devices, self.clock)
        self.acquisition_export = AcquisitionExports(self.devices, self.clock, self.paths)
        self.maintenance = MaintenanceService(self.acquisition)
        self.maintenance_log = MaintenanceLogQueries(self.paths)
        self.diagnostics = DiagnosticsBundles(
            self.paths, self.clock, self.acquisition, self.snapshots, self.maintenance_log
        )
        self.started_at = self.now()

    def now(self) -> str:
        return beijing_iso(self.clock.now())
