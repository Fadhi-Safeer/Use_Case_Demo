"""
Isolated verifier for AlertManager.
Never imports from the live system.
Never calls real aplay/paplay.
Never sleeps.
"""

import sys
import os
import threading
import time

# Ensure we only import from this directory
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from unittest.mock import patch, MagicMock
import alert_manager as _am_module
from alert_manager import AlertManager

SOUND = os.path.join(HERE, "assets", "alert.wav")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

passes = 0
failures = 0

def report(letter, desc, ok, detail=""):
    global passes, failures
    if ok:
        passes += 1
        print(f"PASS \u2713  Scenario {letter}: {desc}")
    else:
        failures += 1
        print(f"FAIL \u2717  Scenario {letter}: {detail}")


def make_am(**kwargs):
    """Construct AlertManager with default sound path inside test dir."""
    kwargs.setdefault("sound_path", SOUND)
    return AlertManager(**kwargs)


def run_sequence(am, sequence, mono_times):
    """
    Drive am.update() with mocked time.monotonic().
    sequence: list of bool
    mono_times: list of float (same length)
    Returns list of bool (return values from update()).
    """
    results = []
    for val, t in zip(sequence, mono_times):
        with patch.object(_am_module.time, "monotonic", return_value=t):
            results.append(am.update(val))
    return results


# ---------------------------------------------------------------------------
# Patch subprocess globally for all tests so _play_alert never exec real audio
# ---------------------------------------------------------------------------

_subprocess_calls = []

def _fake_subprocess_run(cmd, **kwargs):
    _subprocess_calls.append(cmd)
    return MagicMock(returncode=0)


# ---------------------------------------------------------------------------
# Scenarios A–F
# ---------------------------------------------------------------------------

with patch.object(_am_module.subprocess, "run", side_effect=_fake_subprocess_run):

    # --- A: Happy path ---
    am = make_am(consecutive_threshold=4)
    times = [0.0, 2.0, 4.0, 6.0]
    seq   = [True, True, True, True]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    fired_on = [i+1 for i, r in enumerate(results) if r]
    ok = (alert_count == 1 and fired_on == [4] and am.streak == 0)
    report("A", "happy path — alert fires on 4th, streak resets",
           ok, f"expected alert_count=1 fired_on=[4] streak=0, got {alert_count} {fired_on} streak={am.streak}")

    # --- B: Broken by No ---
    am = make_am(consecutive_threshold=4)
    # Yes, Yes, No, Yes, Yes, Yes, Yes
    seq   = [True, True, False, True, True, True, True]
    times = [0.0,  2.0,  4.0,  6.0,  8.0, 10.0, 12.0]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    fired_on = [i+1 for i, r in enumerate(results) if r]
    ok = (alert_count == 1 and fired_on == [7])
    report("B", "broken by No — alert fires only after 4th consecutive Yes post-No",
           ok, f"expected alert_count=1 fired_on=[7], got {alert_count} {fired_on}")

    # --- C: Gap too large ---
    am = make_am(consecutive_threshold=4, max_gap_seconds=10.0)
    # Yes(0), Yes(2), Yes(4), Yes(16)  — gap between 4s and 16s is 12s > 10s
    seq   = [True, True, True, True]
    times = [0.0,  2.0,  4.0,  16.0]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    streak_after = am.streak
    ok = (alert_count == 0 and streak_after == 1)
    report("C", "gap too large — 12s gap resets streak; 4th call starts fresh at 1",
           ok, f"expected alert_count=0 streak=1, got alert_count={alert_count} streak={streak_after}")

    # --- D: Threshold boundary ---
    am = make_am(consecutive_threshold=4)
    seq   = [True, True, True]
    times = [0.0,  2.0,  4.0]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    streak_after = am.streak
    ok = (alert_count == 0 and streak_after == 3)
    report("D", "threshold boundary — Yes×3 produces no alert, streak==3",
           ok, f"expected alert_count=0 streak=3, got alert_count={alert_count} streak={streak_after}")

    # --- E: Sustained threats ---
    am = make_am(consecutive_threshold=4)
    seq   = [True]*8
    times = [float(i*2) for i in range(8)]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    fired_on = [i+1 for i, r in enumerate(results) if r]
    streak_after = am.streak
    ok = (alert_count == 2 and fired_on == [4, 8] and streak_after == 0)
    report("E", "sustained — Yes×8 yields exactly 2 alerts at 4th and 8th",
           ok, f"expected alert_count=2 fired_on=[4,8] streak=0, got {alert_count} {fired_on} streak={streak_after}")

    # --- F: Alternating ---
    am = make_am(consecutive_threshold=4)
    seq   = [True, False, True, False, True, False, True, False]
    times = [float(i*2) for i in range(8)]
    results = run_sequence(am, seq, times)
    alert_count = sum(results)
    streak_after = am.streak
    ok = (alert_count == 0 and streak_after == 0)
    report("F", "alternating Yes/No — 0 alerts",
           ok, f"expected alert_count=0 streak=0, got {alert_count} streak={streak_after}")


# ---------------------------------------------------------------------------
# Constructor guard tests (G–J) — no subprocess patch needed, constructor only
# ---------------------------------------------------------------------------

# --- G: threshold too low ---
try:
    AlertManager(consecutive_threshold=1, sound_path=SOUND)
    report("G", "threshold=1 raises ValueError", False, "expected ValueError, got no exception")
except ValueError:
    report("G", "threshold=1 raises ValueError", True)
except Exception as e:
    report("G", "threshold=1 raises ValueError", False, f"expected ValueError, got {type(e).__name__}: {e}")

# --- H: threshold wrong type ---
try:
    AlertManager(consecutive_threshold="4", sound_path=SOUND)
    report("H", 'threshold="4" raises ValueError', False, "expected ValueError, got no exception")
except ValueError:
    report("H", 'threshold="4" raises ValueError', True)
except Exception as e:
    report("H", 'threshold="4" raises ValueError', False, f"expected ValueError, got {type(e).__name__}: {e}")

# --- I: negative gap ---
try:
    AlertManager(max_gap_seconds=-1, sound_path=SOUND)
    report("I", "max_gap_seconds=-1 raises ValueError", False, "expected ValueError, got no exception")
except ValueError:
    report("I", "max_gap_seconds=-1 raises ValueError", True)
except Exception as e:
    report("I", "max_gap_seconds=-1 raises ValueError", False, f"expected ValueError, got {type(e).__name__}: {e}")

# --- J: missing sound file ---
try:
    AlertManager(sound_path="missing.wav")
    report("J", "missing sound_path raises FileNotFoundError", False, "expected FileNotFoundError, got no exception")
except FileNotFoundError:
    report("J", "missing sound_path raises FileNotFoundError", True)
except Exception as e:
    report("J", "missing sound_path raises FileNotFoundError", False, f"expected FileNotFoundError, got {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Thread-safety smoke test (K)
# ---------------------------------------------------------------------------

with patch.object(_am_module.subprocess, "run", side_effect=_fake_subprocess_run):
    am = make_am(consecutive_threshold=4)
    errors = []

    def _worker():
        try:
            with patch.object(_am_module.time, "monotonic", return_value=1.0):
                am.update(True)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    streak = am.streak
    ok = (len(errors) == 0 and 0 <= streak <= 3)
    report("K", f"thread-safety — 10 threads, no exceptions, streak in [0,3] (got {streak})",
           ok, f"errors={errors}, streak={streak}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

total = passes + failures
print(f"\nRESULT: {passes}/{total} passed")
sys.exit(0 if failures == 0 else 1)
