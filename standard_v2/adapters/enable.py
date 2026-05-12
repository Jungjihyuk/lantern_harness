"""harness enable <name> 엔트리포인트.

disable.py 와 대칭. 자세한 내용은 disable.py 참고.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mutation import run  # noqa: E402


if __name__ == "__main__":
    sys.exit(run("enable"))
