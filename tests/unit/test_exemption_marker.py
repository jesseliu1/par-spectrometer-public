"""The `exemption` marker (tests/exemptions.py) must never hide an expired, incomplete or unrelated failure (R-3-5).

Each case runs a tiny test file in a separate in-process pytest session (`pytester`) with only the exemption
plugin loaded, and checks the reported outcome.
"""

from __future__ import annotations

import sys

import pytest

from tests.exemptions import ExemptedCheck, KnownCheckFailure

pytest_plugins = ["pytester"]

pytestmark = pytest.mark.unit

VALID = 'reason="known", ref="#0", owner="review", expires="2999-12-31"'
EXPIRED = 'reason="known", ref="#0", owner="review", expires="2000-01-01"'


def _run(pytester: pytest.Pytester, marker: str, body: str) -> pytest.RunResult:
    pytester.makeconftest('pytest_plugins = ["tests.exemptions"]\n')
    pytester.makepyfile(f"import pytest\n\n\n@pytest.mark.exemption({marker})\ndef test_case() -> None:\n    {body}\n")
    return pytester.runpytest("-p", "no:cacheprovider", "-rxXf")


def test_valid_exemption_turns_known_assertion_into_xfail(pytester: pytest.Pytester) -> None:
    result = _run(pytester, VALID, "assert 1 == 2")
    result.assert_outcomes(xfailed=1)
    result.stdout.fnmatch_lines(["*known (#0; owner review; expires 2999-12-31)*"])


def test_valid_exemption_does_not_accept_other_exception_types(pytester: pytest.Pytester) -> None:
    _run(pytester, VALID, "raise RuntimeError('unrelated')").assert_outcomes(failed=1)


def test_raises_selects_the_accepted_exception_type(pytester: pytest.Pytester) -> None:
    _run(pytester, f"{VALID}, raises=KeyError", "raise KeyError('k')").assert_outcomes(xfailed=1)
    _run(pytester, f"{VALID}, raises=KeyError", "assert False").assert_outcomes(failed=1)


def test_non_strict_exemption_allows_unexpected_pass(pytester: pytest.Pytester) -> None:
    _run(pytester, VALID, "pass").assert_outcomes(xpassed=1)


def test_strict_exemption_fails_on_unexpected_pass(pytester: pytest.Pytester) -> None:
    _run(pytester, f"{VALID}, strict=True", "pass").assert_outcomes(failed=1)


@pytest.mark.parametrize("body", ["pass", "assert 1 == 2"])
def test_expired_exemption_fails_even_when_the_test_passes(pytester: pytest.Pytester, body: str) -> None:
    result = _run(pytester, EXPIRED, body)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*exemption expired on 2000-01-01*"])


@pytest.mark.parametrize(
    ("marker", "problem"),
    [
        ('reason="known", ref="#0", expires="2999-12-31"', "missing owner"),
        ('reason="", ref="#0", owner="review", expires="2999-12-31"', "missing reason"),
        ('reason="known", ref="#0", owner="review", expires="soon"', "expires 'soon' is not YYYY-MM-DD"),
        (f"{VALID}, platform='darwin'", "unknown field platform"),
        (f"{VALID}, raises='AssertionError'", "raises must be*"),
        (f"{VALID}, platforms='darwin'", "platforms must be*"),
    ],
)
def test_incomplete_or_malformed_exemption_fails_even_when_the_test_passes(
    pytester: pytest.Pytester, marker: str, problem: str
) -> None:
    result = _run(pytester, marker, "pass")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([f"*exemption {problem}*"])


@pytest.mark.parametrize(("body", "outcome"), [("pass", "passed"), ("assert 1 == 2", "failed")])
def test_other_platform_runs_as_ordinary_test(pytester: pytest.Pytester, body: str, outcome: str) -> None:
    result = _run(pytester, f"{VALID}, platforms=['no-such-platform']", body)
    result.assert_outcomes(**{outcome: 1})


def test_listed_platform_is_exempted(pytester: pytest.Pytester) -> None:
    _run(pytester, f"{VALID}, platforms=[{sys.platform!r}]", "assert 1 == 2").assert_outcomes(xfailed=1)


@pytest.mark.parametrize(("body", "outcome"), [("pass", "passed"), ("assert 1 == 2", "failed")])
def test_false_condition_runs_as_ordinary_test(pytester: pytest.Pytester, body: str, outcome: str) -> None:
    _run(pytester, f"{VALID}, condition=False", body).assert_outcomes(**{outcome: 1})


def test_expired_exemption_fails_on_other_platforms_too(pytester: pytest.Pytester) -> None:
    _run(pytester, f"{EXPIRED}, platforms=['no-such-platform']", "pass").assert_outcomes(failed=1)


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_fixture_failure_is_never_exempted(pytester: pytest.Pytester, phase: str) -> None:
    """The exemption covers the call phase only, even for the accepted exception type."""
    pytester.makeconftest('pytest_plugins = ["tests.exemptions"]\n')
    fail_setup = phase == "setup"
    pytester.makepyfile(
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def broken():\n"
        f"    assert not {fail_setup}, 'setup'\n"
        "    yield\n"
        f"    assert {fail_setup}, 'teardown'\n\n\n"
        f"@pytest.mark.exemption({VALID})\n"
        "def test_case(broken) -> None:\n"
        "    assert 1 == 2\n"
    )
    result = pytester.runpytest("-p", "no:cacheprovider", "-rxXfE")
    if fail_setup:
        result.assert_outcomes(errors=1)
    else:
        result.assert_outcomes(xfailed=1, errors=1)
    assert result.ret != 0


def test_collected_checks_all_run_and_are_reported_together() -> None:
    known = ExemptedCheck()
    ran = []

    def check(n: int) -> None:
        ran.append(n)
        assert n == 0, f"check {n}"

    with pytest.raises(KnownCheckFailure, match="2 known check failure.*check 1.*check 2"), known.guard():
        for n in range(3):
            known.collect(check)(n)
    assert ran == [0, 1, 2]


def test_ordinary_assertion_after_collected_failure_still_fails() -> None:
    """A collected known failure must not mask an ordinary assertion later in the same loop."""
    known = ExemptedCheck()

    def check() -> None:
        raise AssertionError("known")

    with pytest.raises(pytest.fail.Exception, match="outside the exempted check.*unrelated"), known.guard():
        known.collect(check)()
        raise AssertionError("unrelated")


def test_collected_checks_that_pass_raise_nothing() -> None:
    known = ExemptedCheck()
    with known.guard():
        known.collect(lambda: None)()


def test_exempted_check_turns_other_assertions_into_failures() -> None:
    known = ExemptedCheck()
    known.collect(lambda: None)()
    with pytest.raises(pytest.fail.Exception, match="outside the exempted check"), known.guard():
        raise AssertionError("unrelated")


def test_exempted_check_leaves_other_exceptions_alone() -> None:
    with pytest.raises(RuntimeError), ExemptedCheck().guard():
        raise RuntimeError("unrelated")


def test_known_check_failure_exemption_rejects_plain_assertions(pytester: pytest.Pytester) -> None:
    """With raises=KnownCheckFailure, an assert outside ExemptedCheck (e.g. unittest setUp) fails normally."""
    marker = f"{VALID}, raises=__import__('tests.exemptions').exemptions.KnownCheckFailure"
    _run(pytester, marker, "assert 1 == 2").assert_outcomes(failed=1)
