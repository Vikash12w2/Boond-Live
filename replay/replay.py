"""
Offline 2021-22 validation replay (spec 13.1):

    python replay/replay.py --weather replay/cache/ludhiana_actual_2021_22.json \
        --crop wheat --sow 2021-11-05 --soil loam

Same as `python -m engine.replay ...`; this file only makes the
command in the spec work from the repository root.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.replay import main  # noqa: E402


if __name__ == "__main__":
    main()
