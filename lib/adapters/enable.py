"""harness enable <name> 엔트리포인트.

disable.py 와 대칭. 자세한 내용은 disable.py 참고.
"""
import sys

from lib.adapters._mutation import run


if __name__ == "__main__":
    sys.exit(run("enable"))
