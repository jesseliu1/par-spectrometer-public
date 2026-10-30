"""Version and names of the 2.0.0-alpha line: the one place an alpha release bumps (internal notes sections 2, 4, 5).

V1.0.x keeps its own par_app/app_info.py (V1.0.3, channel "test"); nothing here is read by V1.0.x and nothing in
app_info is read by the alpha. Every name below differs from its V1.0.3 counterpart so the two versions can sit side by
side on one computer (tests/unit/test_alpha_isolation.py):

  item                 V1.0.3                                        2.0.0-alpha
  program              PAR_Spectrometer.exe                          PAR_Spectrometer_2.exe
  portable folder      PAR_Spectrometer\\                             PAR_Spectrometer_2\\
  archive              PAR_Spectrometer_V1.0.3_trial.zip             PAR_Spectrometer_2.0.0-alpha.N.zip
  data, config, logs   <program folder>\\config, data, logs           %LOCALAPPDATA%\\PAR_Spectrometer_2\\
  config file          config\\app_config.json                        config\\app_config_v2.json
  single-instance      QSharedMemory                                 named mutex
  lock                 VSCO_PAR_PAR_Spectrometer_SingleInstance      Local\\PAR_Spectrometer_2.SingleInstance

par_shell cannot import this module (13_ section 4: the shell talks HTTP only), so it repeats the few names it needs;
tests keep the copies equal. The shell's window title comes from the version the service reports.
"""

from __future__ import annotations

ALPHA_VERSION = "2.0.0-alpha.9"
"""S-1: 2.0.0-alpha.N; bumped when owner tags v2.0.0-alpha.N (web/package.json carries the same string)."""
ALPHA_CHANNEL = "alpha"
"""build_manifest.json "channel" (15_ section 4); V1.0.3 uses "test"."""

APP_NAME = "PAR_Spectrometer_2"
"""Program name, portable folder and data folder name (S-2, 15_ sections 4 and 5)."""
EXE_NAME = f"{APP_NAME}.exe"
ARCHIVE_STEM = "PAR_Spectrometer"
"""The archive is PAR_Spectrometer_<version>.zip, which reads PAR_Spectrometer_2.0.0-alpha.N.zip (15_ section 4)."""
CONFIG_FILE_NAME = "app_config_v2.json"
"""The alpha's own configuration (15_ section 5); V1.0.3's config/app_config.json is never read or written."""

TIER1_CONFIG_FILE_NAME = "app_config.json"
"""The alpha's tier-1 acquisition configuration, in V1.0.3's format but kept in the alpha's own data folder
(<data dir>/config, 16_ 3.1). Read by the support features (D-226) as a file; V1.0.3's program folder is never read."""

PRODUCT_TITLE = "PAR 光谱仪专用软件 ASMART-GROW-SPECTRA I"
"""V1.0.x's window title (par_app/ui.py MainWindow); the alpha appends its version and ALPHA_NOTICE (15_ section 4)."""
ALPHA_NOTICE = "V2.0 试用版"

SINGLE_INSTANCE_NAME = "PAR_Spectrometer_2.SingleInstance"
"""The alpha shell's own single-instance lock (par_shell/instance.py). It never takes V1.0.3's lock: tier 0 opens no
serial port. Tier 1 will have to take V1.0.3's lock as well (13_ section 2.5), which needs owner's approval first."""


def archive_name(version: str = ALPHA_VERSION) -> str:
    """PAR_Spectrometer_2.0.0-alpha.N.zip."""
    return f"{ARCHIVE_STEM}_{version}.zip"


def window_title(version: str = ALPHA_VERSION) -> str:
    """V1.0.x's title + "V2.0 试用版" (S-2, 15_ section 4; issue #119). The build version (`version`, 2.0.0-alpha.N)
    is no longer in the title: customers see the product name; the build stays in build_manifest.json, the
    diagnostics bundle and the top bar's tooltip. Up to alpha.5 the title carried it."""
    del version  # kept for the callers; the title no longer depends on it
    return f"{PRODUCT_TITLE} {ALPHA_NOTICE}"
