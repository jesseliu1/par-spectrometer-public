"""Best-effort redaction of free text in the diagnostics bundle (D-226 问题 3; PR #63 reviews).

Structured data (configuration, settings, status, manifest) is not handled here by pattern: it goes through the
allowlist in bundle_schema.py, and only the strings it keeps pass this Redactor. What is left is free text (service
logs, CSV cells of the device tables), which no pattern set can clean completely; the bundle is for our own
developers and the page asks the user to look at it before sending it outside the company. In this order:

1. Credentials. The running service's token (read from service.json, which itself is never added) becomes <TOKEN>.
   A Cookie / Set-Cookie / Authorization / Proxy-Authorization header line goes entirely. A credential key (one
   ending in password, passwd, pwd, secret, token, api_key, access_key, private_key, authorization, credential(s),
   cookie(s), session_id: db_password, X-PAR-Token, apiKey) followed by ":" or "=" loses the rest of its line,
   whatever the quoting or shape of the value; `Bearer <value>` loses the value. A JSON cell is first scrubbed by key
   (`scrub`), so its structure stays.
2. Known folders, in any case and spelling (either slash, JSON-escaped backslashes, URL-encoded): the alpha data
   directory becomes <DATA_DIR>, the program folder <PROGRAM_DIR>, the user's home folder <HOME>.
3. Any other user folder: `X:\\Users\\<name>` (any drive, any case, 8.3 short names such as ALICE~1 included),
   `/Users/<name>`, `/home/<name>` become <HOME>.
4. Any other absolute Windows path (drive letter; UNC with backslashes, forward slashes, extended-length or URL
   encoding) and a path in a Python traceback line keep only the file name: `<PATH>/North.sqlite3`. In structured
   data (Redactor.structure) a value that is a whole absolute path, POSIX or Windows whatever the host system, keeps
   only its file name unless it lies in the alpha data or program folder - also one under a home folder, whose
   folders after <HOME> would otherwise stay (#66); a folder value (ending in a separator) keeps no name: <PATH>/.

Other POSIX absolute paths in free text are left alone: they cannot be told apart reliably from URL paths
(/api/v0/...) in the service log.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePath
from typing import Any
from urllib.parse import quote

TOKEN_MARK = "<TOKEN>"
SECRET_MARK = "<SECRET>"
DATA_DIR_MARK = "<DATA_DIR>"
HOME_MARK = "<HOME>"
PROGRAM_DIR_MARK = "<PROGRAM_DIR>"
PATH_MARK = "<PATH>"

_WORDS = (
    r"(?:password|passwd|passphrase|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|authorization"
    r"|credentials?|cookies?|session[_-]?id)"
)
_KEY = rf"[\w.-]*?{_WORDS}(?![\w.-])"
"""A credential key: one that ENDS with a credential word (db_password, X-PAR-Token, apiKey, session-id), so counts
and error texts named after one (token_count, password_retries, last_token_error) are kept (rv-63b nit)."""
SECRET_KEY = re.compile(rf"^{_KEY}$", re.IGNORECASE)
SETTING_NAME_FIELDS = ("key", "name")
"""A {"key": <name>, "value": ...} row (app_settings as exported): a credential name hides its "value"."""
SETTING_VALUE_FIELD = "value"


_MARKED = r"(?![\s\"'\\]*<(?:SECRET|TOKEN)>)"
"""Not already replaced (a JSON cell scrubbed by key keeps its structure)."""
_TEXT_RULES = (
    # a credential header line (Cookie, Set-Cookie, Authorization, Proxy-Authorization) goes entirely; no "$": it
    # would not match before the CR of a CRLF line end (Windows logs, #66), and [^\r\n]* runs to the line end anyway
    re.compile(
        r"^[^\r\n]*(?<![\w-])(?:Set-Cookie|Cookie|Proxy-Authorization|Authorization)[\s\"'\\]*[:=][^\r\n]*",
        re.IGNORECASE | re.MULTILINE,
    ),
    # a credential key followed by ":" or "=": the rest of the line goes, whatever its quoting or shape
    re.compile(rf"(?<![\w.-])(?P<key>{_KEY})(?P<sep>[\s\"'\\]*[:=]){_MARKED}[^\r\n]*", re.IGNORECASE),
    re.compile(r"(?P<head>(?<![\w-])Bearer\s+)[^\s\"',;<>]+", re.IGNORECASE),
)
HEADER_LINE_MARK = f"{SECRET_MARK} [credential header line removed]"
REST_OF_LINE = " [rest of line removed]"

_SEP = r"(?:\\|/|%5[cC]|%2[fF])"
_NOT_SEP = r"(?!%5[cC]|%2[fF])"
_DRIVE = r"(?<![A-Za-z0-9])[A-Za-z](?::|%3[aA])"
_NAME_CHAR = r"[^\\/\"'<>|:*?\r\n]"
_NAME_EDGE = r"[^\\/\s\"'<>|:*?]"
_PART = rf"(?:{_NOT_SEP}{_NAME_EDGE}(?:(?:{_NOT_SEP}{_NAME_CHAR})*{_NOT_SEP}{_NAME_EDGE})?)"
"""A middle folder name of a Windows path: spaces inside allowed ("Program Files"), not at either end."""
_LAST = rf"(?:{_NOT_SEP}[^\\/\s\"'<>|:*?,;()\[\]])*"
"""The last name of a path (the file name): ends at a space, quote or punctuation."""
_USER = rf"(?:{_PART}(?={_SEP})|{_LAST})"
_GENERIC_RULES = (
    (re.compile(rf"{_DRIVE}{_SEP}+(?:Users|Documents and Settings){_SEP}+{_USER}", re.IGNORECASE), HOME_MARK),
    (re.compile(r"(?<![\w.-])/(?:Users|home)/[^/\s\"'<>|:]+", re.IGNORECASE), HOME_MARK),
)
_UNC_START = r"(?<![\w:\\/%>])(?:(?:\\\\){1,2}|%5[cC]%5[cC]|//|%2[fF]%2[fF])"
"""Two backslashes (four when JSON-escaped), two forward slashes (not after "scheme:"), or their URL encoding."""
_EXTENDED_UNC = rf"(?:(?:\?|%3[fF]){_SEP}+UNC{_SEP}+)?"
r"""The extended-length prefix \\?\UNC\ (\\?\C:\ is a drive path and caught by the drive rule)."""
_ABSOLUTE = (
    re.compile(rf"{_DRIVE}{_SEP}+(?:{_PART}{_SEP}+)*(?P<name>{_LAST})"),
    re.compile(rf"{_UNC_START}{_EXTENDED_UNC}[\w.$-]+{_SEP}+(?:{_PART}{_SEP}+)*(?P<name>{_LAST})", re.IGNORECASE),
    re.compile(r'(?<=File ")/(?:[^"/\r\n]+/)+(?P<name>[^"/\r\n]+)(?=")'),
)
r"""Other absolute paths keep only their file name: drive letter, UNC (also \\?\UNC\ and %5C%5C), and a POSIX path in
a Python traceback line (File "/srv/site/app.py") where it cannot be a URL path."""
SHORT_PATH_CHARS = 1024
"""Buffer for GetShortPathNameW (characters); a longer short path is simply not added."""
_FOLDER_END = r"(?![\w.~$-])"
_POSIX_PATH = re.compile(r"/(?:[^/\r\n]+/)+[^/\r\n]*")
"""A whole value that is an absolute POSIX path with at least one folder (/a/b), as a configuration stores it."""
_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\r\n]*|[\\/]{2}[^\\/\r\n][^\r\n]*")
r"""A whole value that is an absolute Windows path: drive letter (C:\ or C:/), UNC (\\server\share, //server/share)
or extended length (\\?\C:\, \\?\UNC\), checked on the text itself on every host system (#66)."""
_KEPT_FOLDERS = (DATA_DIR_MARK, PROGRAM_DIR_MARK)
"""Structured paths inside these folders keep their folders (they are the alpha's own); any other absolute path,
also one under a home folder, keeps only its file name."""


def _mark_for(key: str) -> str:
    return TOKEN_MARK if "token" in key.lower() or key.lower() == "bearer" else SECRET_MARK


def scrub(value: Any) -> Any:  # noqa: ANN401 (any JSON value)
    """A copy of `value` with every credential key's value replaced (None stays None)."""
    if isinstance(value, Mapping):
        setting = _names_a_credential(value)
        cleaned = {}
        for key, item in value.items():
            if SECRET_KEY.match(str(key)) or (setting and key == SETTING_VALUE_FIELD):
                name = str(key) if SECRET_KEY.match(str(key)) else str(_setting_name(value))
                cleaned[key] = None if item is None else _mark_for(name)
            else:
                cleaned[key] = scrub(item)
        return cleaned
    if isinstance(value, list | tuple):
        return [scrub(item) for item in value]
    return value


def _setting_name(value: Mapping[Any, Any]) -> object:
    return next((value[field] for field in SETTING_NAME_FIELDS if field in value), None)


def _names_a_credential(value: Mapping[Any, Any]) -> bool:
    name = _setting_name(value)
    return SETTING_VALUE_FIELD in value and isinstance(name, str) and bool(SECRET_KEY.match(name))


def _folder_pattern(folder: str) -> re.Pattern[str] | None:
    """`folder` in any case, with any separator (also doubled or URL-encoded), its names also URL-encoded."""
    names = [name for name in re.split(r"[\\/]+", folder) if name]
    if not names or (len(names) == 1 and not re.fullmatch(r"[A-Za-z]:", names[0])):
        return None  # never a root folder: it would rewrite every path
    parts = []
    for name in names:
        if re.fullmatch(r"[A-Za-z]:", name):
            parts.append(rf"(?<![A-Za-z0-9]){re.escape(name[0])}(?::|%3[aA])")
            continue
        spellings = {re.escape(name), re.escape(quote(name, safe=""))}
        parts.append("(?:" + "|".join(sorted(spellings)) + ")")
    lead = "" if re.fullmatch(r"[A-Za-z]:", names[0]) else f"{_SEP}+"
    return re.compile(lead + f"{_SEP}+".join(parts) + _FOLDER_END, re.IGNORECASE)


def _short_name(folder: Path) -> str | None:
    """The 8.3 spelling Windows may use for the folder (TEMP often is C:\\Users\\ALICE~1\\...); None elsewhere."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes  # noqa: PLC0415 (Windows only)

        buffer = ctypes.create_unicode_buffer(SHORT_PATH_CHARS)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(folder), buffer, len(buffer))
    except (AttributeError, OSError):
        return None
    return buffer.value if 0 < length < len(buffer) else None


def program_folder() -> Path | None:
    """The packaged alpha's own folder (PAR_Spectrometer_2\\, where tools/alpha_release.py writes build_manifest.json);
    None when run from source. V1.0.3's program folder is never looked at (tests/unit/test_alpha_isolation.py)."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def service_token(service_file: Path) -> str | None:
    """The running service's token, read only to remove it from the bundle (service.json itself is never added)."""
    try:
        token = json.loads(service_file.read_text(encoding="utf-8")).get("token")
    except (OSError, ValueError, AttributeError):
        return None
    return token if isinstance(token, str) and token else None


class Redactor:
    """Removes credentials and local folders from a text (see the module description for the rules)."""

    def __init__(self, token: str | None, folders: Iterable[tuple[str | PurePath, str]]) -> None:
        self.token = token
        unique = {(str(folder), mark) for folder, mark in folders if str(folder)}
        ordered = sorted(unique, key=lambda item: len(item[0]), reverse=True)  # the data directory lies inside home
        self.folders = [(pattern, mark) for folder, mark in ordered if (pattern := _folder_pattern(folder))]

    @classmethod
    def for_paths(cls, paths: Any, home: Path | None = None) -> Redactor:  # noqa: ANN401 (AlphaPaths)
        folders: list[tuple[str | PurePath, str]] = []
        homes = [home] if home is not None else [Path.home(), *_env_folders("USERPROFILE")]
        program = program_folder()
        known: list[tuple[Path, str]] = [(paths.data_dir, DATA_DIR_MARK), *((item, HOME_MARK) for item in homes)]
        if program is not None:
            known.append((program, PROGRAM_DIR_MARK))
        for folder, mark in known:
            for spelling in (folder, _resolved(folder), _short_name(folder)):
                if spelling is not None:
                    folders.append((spelling, mark))
        return cls(service_token(paths.service_file), folders)

    def __call__(self, text: str) -> str:
        if self.token:
            text = text.replace(self.token, TOKEN_MARK)
        header, key_rest, bearer = _TEXT_RULES
        text = header.sub(HEADER_LINE_MARK, text)
        text = key_rest.sub(_drop_rest, text)
        text = bearer.sub(lambda match: match.group("head") + TOKEN_MARK, text)
        if not any(mark in text for mark in (":", "/", "\\", "%")):
            return text
        for pattern, mark in self.folders:
            text = pattern.sub(mark, text)
        for pattern, mark in _GENERIC_RULES:
            text = pattern.sub(mark, text)
        for pattern in _ABSOLUTE:
            text = pattern.sub(lambda match: f"{PATH_MARK}/{match.group('name')}", text)
        return text

    def structure(self, value: Any) -> Any:  # noqa: ANN401 (any JSON value)
        """A copy of structured data: credential keys scrubbed, every string redacted, and a string that is a whole
        absolute path - POSIX or Windows, whatever the host system - outside the alpha data and program folders (a
        database path outside the alpha folder, also one under the user's home) reduced to its file name (#66)."""
        return self._leaves(scrub(value))

    def _leaves(self, value: Any) -> Any:  # noqa: ANN401
        if isinstance(value, dict):
            return {key: self._leaves(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._leaves(item) for item in value]
        if isinstance(value, str):
            text = self(value)
            if text.startswith(_KEPT_FOLDERS) or not _is_whole_path(value):
                return text
            names = [name for name in re.split(r"[\\/]", text) if name]  # of the redacted text
            if names == [HOME_MARK]:
                return text  # a home folder alone stays <HOME>
            folder = text.endswith(("/", "\\"))  # a folder keeps no name at all (review of PR #68)
            return f"{PATH_MARK}/" if folder else f"{PATH_MARK}/{names[-1]}"
        return value

    def cell(self, value: Any) -> Any:  # noqa: ANN401 (a database value)
        """One table cell: a JSON object or list is scrubbed by key before the text rules; numbers stay numbers."""
        if not isinstance(value, str):
            return value
        if value[:1] in ("{", "["):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError):
                parsed = None
            if isinstance(parsed, dict | list):
                cleaned = self.structure(parsed)
                if cleaned != parsed:
                    value = json.dumps(cleaned, ensure_ascii=False)
        return self(value)


def _is_whole_path(value: str) -> bool:
    """Whether the whole value is an absolute POSIX or Windows path (whatever the host system)."""
    return bool(_POSIX_PATH.fullmatch(value) or _WINDOWS_PATH.fullmatch(value))


def _drop_rest(match: re.Match[str]) -> str:
    return f"{match.group('key')}{match.group('sep')} {_mark_for(match.group('key'))}{REST_OF_LINE}"


def _resolved(folder: Path) -> Path | None:
    try:
        return folder.resolve()
    except OSError:
        return None


def _env_folders(*names: str) -> list[Path]:
    return [Path(value) for name in names if (value := os.environ.get(name))]
