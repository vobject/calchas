import datetime
import logging
import pprint
import queue
import shutil
import signal
import sys
import threading
import time
from typing import Any, Dict

from calchas.common import base


class Monitor(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)
        self.request_stop = False

        self._health_check_thread = None
        self._shutdown_callbacks = []

    def on_process_message(self, msg: base.Message):
        logging.debug(f"Monitor msg from {msg.sensor.name}")

        # if msg.sensor.name == "systeminfo":
        #    logging.info(pprint.pformat(msg.data, indent=4))

    def on_signal(self, signal_number=0, stack_frame=None):
        logging.info(f"Signal received {signal_number}. Informing {len(self._shutdown_callbacks)} listeners.")
        for cb in self._shutdown_callbacks:
            cb()
        logging.info(f"Signal {signal_number} processed.")

    def register_shutdown_callback(self, cb):
        if cb not in self._shutdown_callbacks:
            self._shutdown_callbacks.append(cb)

    def _start_impl(self):
        self.request_stop = False

        self._run_health_check()
        if self.request_stop:
            raise OSError("Failed to start health monitor because initial health check failed.")

        self._health_check_thread = threading.Thread(target=self._health_check_thread_fn)
        self._health_check_thread.start()

        self._orig_handler_sigint = signal.signal(signal.SIGINT, self.on_signal)
        self._orig_handler_sigterm = signal.signal(signal.SIGTERM, self.on_signal)

    def _stop_impl(self):
        self.request_stop = True

        if self._health_check_thread:
            self._health_check_thread.join()
            self._health_check_thread = None

        signal.signal(signal.SIGINT, self._orig_handler_sigint)
        signal.signal(signal.SIGTERM, self._orig_handler_sigterm)

    def _health_check_thread_fn(self):
        frequency_sleep_sec = 1. / self.options.get("frequency", 1.)
        while not self.request_stop:
            self._run_health_check()

            if self.request_stop:
                logging.info(f"Health check failed. Informing {len(self._shutdown_callbacks)} listeners.")
                for cb in self._shutdown_callbacks:
                    cb()
                break

            time.sleep(frequency_sleep_sec - time.time() % frequency_sleep_sec)

    def _run_health_check(self):
        if self.request_stop:
            return

        total, used, _free = shutil.disk_usage(self.options["out_dir"])
        percent = round((used / total) * 100., 1)

        if not self.dry_run and (percent > self.options["disk_usage_threshold"]):
            logging.info(f"Shutting down because disk usage is at {percent}% ({self.options['disk_usage_threshold']}% allowed)")
            self.request_stop = True
