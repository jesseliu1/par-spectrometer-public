"""Write the OpenAPI schema of the local service to docs/spec/openapi-v0.json (api-contract-v0 section 5).

Usage: python tools/export_openapi.py [--check]
Every interface change must show up as a diff of that file; tests/api/test_openapi.py fails while it is stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from par_app.api.app import openapi_document  # noqa: E402

TARGET = ROOT / "docs" / "spec" / "openapi-v0.json"


def render() -> str:
    return json.dumps(openapi_document(), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the stored schema differs from the code")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"{TARGET.relative_to(ROOT)} is stale: run python tools/export_openapi.py")
            return 1
        print("openapi schema up to date")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
