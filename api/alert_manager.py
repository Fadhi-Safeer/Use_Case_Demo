import threading
import time
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class AlertManager:

    def __init__(
        self,
        consecutive_threshold: int = 4,
        max_gap_seconds: float = 10.0,
        sound_path: str = "assets/alert.wav",
    ):
        if not isinstance(consecutive_threshold, int) or consecutive_threshold < 2:
            raise ValueError("consecutive_threshold must be an integer >= 2")
        if not isinstance(max_gap_seconds, (int, float)) or max_gap_seconds <= 0:
            raise ValueError("max_gap_seconds must be a positive number")
        sound_file = Path(sound_path)
        if not sound_file.exists():
            raise FileNotFoundError(f"Alert sound not found: {sound_path}")

        self.threshold = consecutive_threshold
        self.max_gap = max_gap_seconds
        self.sound_path = str(sound_file)
        self._lock = threading.Lock()
        self._streak: int = 0
        self._last_threat_ts: float | None = None
        self._is_playing = False

    def update(self, is_threat: bool) -> bool:
        now = time.monotonic()
        triggered = False

        with self._lock:
            if is_threat:
                if self._last_threat_ts is not None:
                    gap = now - self._last_threat_ts
                    if gap > self.max_gap:
                        self._streak = 0
                self._streak += 1
                self._last_threat_ts = now
                if self._streak >= self.threshold:
                    triggered = True
            else:
                self._streak = 0
                self._last_threat_ts = None

        if triggered:
            self._play_alert()

        return triggered

    def _play_alert(self):
        # Sound moved to browser — see static/alert.wav
        # if self._is_playing:
        #     return
        #
        # def _play():
        #     self._is_playing = True
        #     try:
        #         subprocess.run(["aplay", "-q", self.sound_path], timeout=10, check=True)
        #     except FileNotFoundError:
        #         try:
        #             subprocess.run(["paplay", self.sound_path], timeout=10, check=True)
        #         except Exception as e:
        #             logger.error("Sound playback failed: %s", e)
        #     except Exception as e:
        #         logger.error("Playback error: %s", e)
        #     finally:
        #         self._is_playing = False
        #
        # t = threading.Thread(target=_play, daemon=True, name="alert-sound")
        # t.start()
        pass

    @property
    def streak(self) -> int:
        with self._lock:
            return self._streak

    @property
    def config(self) -> dict:
        return {
            "consecutive_threshold": self.threshold,
            "max_gap_seconds": self.max_gap,
            "sound_path": self.sound_path,
        }
