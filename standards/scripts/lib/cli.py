"""Exit codes and stdout emission shared by every script in this repository.

Distinct exit codes per failure class exist so a caller -- CI, a pre-commit
hook, or an agent -- can branch without scraping human-readable text. The
distinction that matters most is between :data:`EXIT_FINDINGS` (the script ran
correctly and the *repository* is wrong) and :data:`EXIT_USAGE` /
:data:`EXIT_INTERNAL` (the script itself could not do its job). Collapsing
those into a single non-zero code is how a broken validator gets mistaken for
a clean run, or a clean run for a broken validator.
"""

from __future__ import annotations

import json
import sys
from typing import Any

#: Everything checked, nothing to report.
EXIT_OK = 0
#: The script ran to completion and found problems in the repository.
EXIT_FINDINGS = 1
#: Bad invocation: unknown flag, missing required argument, contradictory options.
EXIT_USAGE = 2
#: A required input does not exist or is unreadable (missing path, missing config).
EXIT_INPUT = 3
#: An input exists but is malformed (unparseable YAML/JSON, schema-invalid config).
EXIT_MALFORMED = 4
#: An unexpected internal failure, including a missing third-party dependency.
EXIT_INTERNAL = 5

EXIT_CODE_HELP = """exit codes:
  0  success, no findings
  1  findings reported (the repository needs a change)
  2  usage error (bad or contradictory arguments)
  3  a required input was missing or unreadable
  4  a required input was malformed
  5  internal error, including a missing dependency
"""


def emit(payload: Any) -> None:
    """Write ``payload`` to stdout as a single JSON document plus a newline.

    Uses ``sys.stdout.write`` rather than ``print`` so that the no-``print``
    lint rule can stay absolute: any ``print`` in this repository is a bug,
    with no exceptions to reason about.
    """
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
