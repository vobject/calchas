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
from calchas.ui import menu


class Monitor(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)
        self.request_stop = False

        self._render_thread = None

        self.menu = None

    def on_process_message(self, msg: base.Message):
        self.menu.update(msg)

    def _start_impl(self):
        self.request_stop = False

        # TODO: find a better place for this...
        self.menu = menu.Menu()
        # TODO: find a way of adding only active sensors (what about using "offer()" -> "display")
        for sensor_name in self.options.get("screens", []):
            self.menu.add_screen(sensor_name)

        self._render_thread = threading.Thread(target=self._render_thread_fn)
        self._render_thread.start()

    def _stop_impl(self):
        self.request_stop = True

        if self._render_thread:
            self._render_thread.join()
            self._render_thread = None

        self.menu.exit()

    def _render_thread_fn(self):
        sleep_sec = 1. / self.options.get("framerate", 1.)

        while not self.request_stop:
            self.menu.display()
            time.sleep(sleep_sec - time.time() % sleep_sec)
