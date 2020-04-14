import collections
import datetime
import logging
import queue
import shutil
import signal
import sys
import threading
import time
from typing import Any, Dict

from calchas import trip, utils
from calchas.ui import menu


class HealthEntry:
    def __init__(self, sensor: Any, state: Any):
        self.time = time.time()
        self.sensor = sensor
        self.state = state

    def __repr__(self) -> str:
        return f"{datetime.datetime.fromtimestamp(self.time): {self.state}}"

    def __str__(self) -> str:
        return self.__repr__()


class HealthMonitor:
    def __init__(self, trip: trip.Trip, options: Dict[str, Any]=None):
        self.trip = trip
        self.options = utils.dict_merge(self.default_options(), options)
        self.request_stop = False

        self._entries = queue.Queue()
        self._consume_entries_thread = None
        self._health_check_thread = None
        self._shutdown_callbacks = []

        self.menu = None

    def __enter__(self):
        self._run_health_check()
        if self.request_stop:
            raise OSError("Failed to start health monitor because initial health check failed.")

        # TODO: find a better place for this...
        self.menu = menu.Menu()
        for sensor_name, sensor_options in self.trip.options.items():
            if sensor_options.get("active", False):
                self.menu.add_screen(sensor_name)

        self._start()

        self._orig_handler_sigint = signal.signal(signal.SIGINT, self.on_signal)
        self._orig_handler_sigterm = signal.signal(signal.SIGTERM, self.on_signal)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop()

        self.menu.exit()

        signal.signal(signal.SIGINT, self._orig_handler_sigint)
        signal.signal(signal.SIGTERM, self._orig_handler_sigterm)

    def default_options(self) -> Dict[str, Any]:
        return {
            # Shut down when there's less than 5% percent disk space available.
            "disk_usage_threshold": 95.0,
        }

    def on_report(self, entry: HealthEntry):
        self._entries.put(entry)

    def on_signal(self, signal_number=0, stack_frame=None):
        logging.info(f"Signal received {signal_number}. Informing {len(self._shutdown_callbacks)} listeners.")
        for cb in self._shutdown_callbacks:
            cb()
        logging.info(f"Signal {signal_number} processed.")

    def register_shutdown_callback(self, cb):
        if cb not in self._shutdown_callbacks:
            self._shutdown_callbacks.append(cb)

    def _start(self):
        logging.info("Starting health monitor")
        self.request_stop = False

        self._health_check_thread = threading.Thread(target=self._health_check_thread_fn)
        self._health_check_thread.start()

        self._consume_entries_thread = threading.Thread(target=self._consume_entries_thread_fn)
        self._consume_entries_thread.start()

    def _stop(self):
        logging.info("Stopping health monitor")
        self.request_stop = True

        if self._health_check_thread:
            self._health_check_thread.join()
            self._health_check_thread = None

        if self._consume_entries_thread:
            self._consume_entries_thread.join()
            self._consume_entries_thread = None

        self._entries = queue.Queue()
        logging.info("Stopped health monitor")

    def _health_check_thread_fn(self):
        while not self.request_stop:
            self._run_health_check()

            if self.request_stop:
                logging.info(f"Health check failed. Informing {len(self._shutdown_callbacks)} listeners.")
                for cb in self._shutdown_callbacks:
                    cb()
                break

            self.menu.display()
            time.sleep(.5)

    def _consume_entries_thread_fn(self):
        while not self.request_stop:
            try:
                entry = self._entries.get(True, 1.)
            except queue.Empty:
                continue

            if entry.sensor.name == "systeminfo":
                logging.info(entry.state)

            self.menu.update(entry)

            # logging.info(
            #     f"PROCESS: {entry.state['process']['cpu_percent']}% RSS={entry.state['process']['mem_rss'] // 1024}KiB VMS={entry.state['process']['mem_vms'] // 1024}KiB "
            #     f"DISK: {entry.state['filesystem'][obj.options['partition']]['percent']}% "
            #     f"TEMP: CPU={entry.state['temperature']['cpu']:.2f}°C GPU={entry.state['temperature']['gpu']:.2f}°C"
            # )

    def _run_health_check(self):
        if self.request_stop:
            return

        total, used, _free = shutil.disk_usage(self.trip.parent_dir)
        percent = round((used / total) * 100., 1)

        if percent > self.options["disk_usage_threshold"]:
            logging.info(f"Shutting down because disk usage is at {percent}% ({self.options['disk_usage_threshold']}% allowed)")
            self.request_stop = True
