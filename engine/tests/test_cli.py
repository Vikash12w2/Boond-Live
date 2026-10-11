import json
import subprocess
import sys
from pathlib import Path

import pytest

from engine import replay as replay_module
from engine import simulate as simulate_module


ROOT = Path(__file__).resolve().parents[2]
WEATHER = str(ROOT / "replay" / "cache" / "ludhiana_actual_2021_22.json")


@pytest.mark.parametrize(
    "args, profile",
    [
        (["--crop", "wheat", "--sow", "2021-11-05"], "wheat"),
        (["--crop", "wheat", "--sow", "2021-12-10"], "wheat_late"),
        (["--crop", "wheat", "--sow", "2021-12-10", "--exact-profile"], "wheat"),
        (["--crop", "wheat_late", "--sow", "2021-12-01"], "wheat_late"),
        (["--crop", "paddy", "--sow", "2021-06-25", "--variety", "PR 126"], "paddy_short"),
        (["--crop", "cotton", "--sow", "2021-05-01"], "cotton"),
    ],
)
def test_replay_cli_picks_the_profile_like_registration(tmp_path, capsys, args, profile):
    result = replay_module.main(["--weather", WEATHER, "--soil", "loam",
                                 "--out-dir", str(tmp_path), *args])

    assert result["profile"] == profile
    assert result["boond"]["crop"] == profile
    assert (tmp_path / f"replay_{profile}_loam.json").exists()


def test_simulate_cli_picks_the_late_wheat_profile(capsys):
    result = simulate_module.main(["--weather", WEATHER, "--crop", "wheat", "--sow", "2021-12-10"])

    assert result["summary"]["crop"] == "wheat_late"
    assert len(result["days"]) == 133


def test_spec_replay_command_runs_from_the_repo_root(tmp_path):
    completed = subprocess.run(
        [sys.executable, "replay/replay.py", "--weather", WEATHER, "--crop", "wheat",
         "--sow", "2021-11-05", "--soil", "loam", "--out-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    saved = json.loads((tmp_path / "replay_wheat_loam.json").read_text())
    assert saved["label"].startswith("SIMULATION")
