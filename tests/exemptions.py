"""Named, time-limited exemptions for known test failures (R-3-5), loaded as a plugin by tests/conftest.py.

``@pytest.mark.exemption(reason=..., ref=..., owner=..., expires="YYYY-MM-DD", ...)``

* ``reason``, ``ref``, ``owner`` and ``expires`` are required. A missing or empty field, an unknown keyword, a
  malformed value or a past ``expires`` makes the test FAIL in its call phase, even when the test body would
  pass, until the test is fixed or the exemption is renewed with approval.
* ``raises`` (default ``AssertionError``; a type or a tuple of types): the only exception the exemption accepts.
  Any other exception is an ordinary failure.
* ``platforms`` (optional list of ``sys.platform`` values, e.g. ``["darwin"]``): exempt only there; on other
  platforms the test runs as an ordinary test.
* ``condition`` (optional bool, default True): exempt only while it is true (e.g. an offscreen-only limit);
  otherwise the test runs as an ordinary test.
* ``strict`` (optional bool, default False): also fail when the test unexpectedly passes (stale assertions that
  must be rewritten, not merely re-measured).

Inside its window an applicable exemption is an ``xfail(raises=..., strict=...)`` that covers the call phase only:
a failing fixture (setup or teardown) is an ordinary error even when it raises the accepted type. When the known
failure is one check inside a longer scenario, run that check through `ExemptedCheck.collect` and declare
``raises=KnownCheckFailure``: only the collected check can then reach the exemption, and every other assertion of
the scenario (including ``unittest`` ``setUp``/cleanups) stays an ordinary failure. Collect exactly one known
assertion per call and keep every other check of the same loop outside it: a collected failure never stops the
scenario, so the remaining sizes, iterations and ordinary checks still run.
Unit tests: tests/unit/test_exemption_marker.py.
"""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from typing import ParamSpec

import pytest

REQUIRED = ("reason", "ref", "owner", "expires")
OPTIONAL = ("raises", "platforms", "condition", "strict")
_PROBLEM = pytest.StashKey[str]()
_EXEMPTED = pytest.StashKey[bool]()
P = ParamSpec("P")


def _is_exception_types(value: object) -> bool:
    values = value if isinstance(value, tuple) else (value,)
    return bool(values) and all(isinstance(v, type) and issubclass(v, BaseException) for v in values)


def exemption_problem(args: tuple[object, ...], kwargs: Mapping[str, object], today: date) -> str | None:
    """Why the exemption is invalid, or None when it is valid on ``today``."""
    if args:
        return "takes keyword arguments only"
    missing = [key for key in REQUIRED if not kwargs.get(key)]
    if missing:
        return f"missing {', '.join(missing)}"
    unknown = sorted(set(kwargs) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        return f"unknown field {', '.join(unknown)}"
    try:
        expires = date.fromisoformat(str(kwargs["expires"]))
    except ValueError:
        return f"expires {kwargs['expires']!r} is not YYYY-MM-DD"
    if today > expires:
        return f"expired on {expires}"
    if not _is_exception_types(kwargs.get("raises", AssertionError)):
        return "raises must be an exception type or a tuple of exception types"
    platforms = kwargs.get("platforms")
    if platforms is not None and (
        isinstance(platforms, str)
        or not isinstance(platforms, Iterable)
        or not all(isinstance(name, str) and name for name in platforms)
    ):
        return "platforms must be a list of sys.platform values"
    for flag in ("condition", "strict"):
        if not isinstance(kwargs.get(flag, False), bool):
            return f"{flag} must be True or False"
    return None


def apply_exemptions(items: Iterable[pytest.Item], today: date, platform: str) -> None:
    """Turn valid, applicable exemptions into xfail; remember invalid ones for `pytest_runtest_call`."""
    for item in items:
        marker = item.get_closest_marker("exemption")
        if marker is None:
            continue
        info = marker.kwargs
        problem = exemption_problem(marker.args, info, today)
        if problem is not None:
            item.stash[_PROBLEM] = problem
            continue
        platforms = info.get("platforms")
        if not info.get("condition", True) or (platforms is not None and platform not in platforms):
            continue
        reason = f"{info['reason']} ({info['ref']}; owner {info['owner']}; expires {info['expires']})"
        raises = info.get("raises", AssertionError)
        item.add_marker(pytest.mark.xfail(reason=reason, raises=raises, strict=info.get("strict", False)))
        item.stash[_EXEMPTED] = True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    apply_exemptions(items, date.today(), sys.platform)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    problem = item.stash.get(_PROBLEM, None)
    if problem is not None:
        pytest.fail(f"exemption {problem}: fix the test, or renew the exemption with approval (R-3-5)", pytrace=False)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """An exemption never covers setup or teardown: a fixture failure there is reported as an ordinary error."""
    report: pytest.TestReport = yield
    if call.when != "call" and call.excinfo is not None and item.stash.get(_EXEMPTED, False):
        if hasattr(report, "wasxfail"):
            del report.wasxfail
            report.outcome = "failed"
    return report


def _name(check: Callable[..., None]) -> str:
    return getattr(check, "__qualname__", None) or repr(check)


class KnownCheckFailure(Exception):
    """A check run through `ExemptedCheck` failed; the exception its exemption declares (``raises=``).

    Deliberately not an AssertionError, so a plain ``assert`` anywhere else in the test never matches it.
    """


class ExemptedCheck:
    """Confines an exemption to the known checks of a longer scenario.

    A check passed through `collect` (one known assertion) records its failure and lets the scenario continue;
    `guard()` raises a single `KnownCheckFailure` listing every recorded failure once the scenario has finished.
    Inside `guard()` any other AssertionError (replayed steps, sibling checks, screenshots) is reported as an
    ordinary failure. There is deliberately no variant that stops at the first known failure: it would skip the
    remaining sizes and iterations, and with them every ordinary check they contain.
    """

    def __init__(self) -> None:
        self._failures: list[str] = []

    def collect(self, check: Callable[P, None]) -> Callable[P, None]:
        @functools.wraps(check)
        def exempted(*args: P.args, **kwargs: P.kwargs) -> None:
            try:
                check(*args, **kwargs)
            except AssertionError as error:
                self._failures.append(f"{_name(check)}: {error!r}")

        return exempted

    @contextmanager
    def guard(self) -> Iterator[None]:
        try:
            yield
        except AssertionError as error:
            pytest.fail(f"assertion outside the exempted check failed (not covered by the exemption): {error!r}")
        if self._failures:
            raise KnownCheckFailure(f"{len(self._failures)} known check failure(s): " + "; ".join(self._failures))
