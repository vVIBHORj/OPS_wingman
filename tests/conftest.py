"""
Global pytest configuration and fixtures for OpsWingman.
"""

import sys
from pathlib import Path
import pytest

# Ensure repository root is added to sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
