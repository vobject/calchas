import logging
from typing import Any

from calchas import monitor


class MonitoredSensor:
    def __init__(self, options: Any, healthmon: monitor.HealthMonitor):
        super().__init__()
        self._options = options
        self._healthmon = healthmon
        self._dry_run = "dry-run" in options and options["dry-run"] is True

    @property
    def name(self):
        return self.options["name"]

    @property
    def options(self):
        return self._options

    @property
    def dry_run(self):
        return self._dry_run

    @property
    def out_dir(self):
        return self.options["out_dir"]

    def monitor(self, entry: Any):
        self._healthmon.on_report(monitor.HealthEntry(self, entry))

    def start(self):
        try:
            self._start_impl()
        except Exception:
            logging.exception(f"Error starting {self.name}")

    def stop(self):
        try:
            self._stop_impl()
        except Exception:
            logging.exception(f"Error stopping {self.name}")

    def _start_impl(self):
        raise NotImplementedError

    def _stop_impl(self):
        raise NotImplementedError
