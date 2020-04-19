import csv
import datetime
import logging
import os
import platform
import subprocess
import threading
import time
from typing import Any, Dict, List

import psutil

from calchas.sensors import base


class Sensor(base.Publisher):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.impl = None
        self.read_thread = None
        self.request_stop = False

    def offer(self) -> List[str]:
        # TODO: support topics
        return ["all"]

    def _start_impl(self) -> None:
        if not self.impl:
            if platform.system() == "Linux" and os.uname()[4][:3] == "arm":  # TODO: identify raspberry pi
                self.impl = SensorImplRaspi(self.out_dir)
            else:
                # Generic implementation
                self.impl = SensorImpl(self.out_dir)

        self.request_stop = False
        if not self.read_thread:
            logging.info("Starting system info thread...")
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"System info thread started.")

    def _stop_impl(self) -> None:
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

    def _read_thread_fn(self) -> None:
        frequency_sleep_sec = 1. / self.options.get("frequency", 1.)
        while not self.request_stop:
            data = {}
            data.update(self.impl.read_system())
            data.update(self.impl.read_process())
            data.update(self.impl.read_disk())

            # TODO: create classes for payload-types
            self.publish("all", data)

            time.sleep(frequency_sleep_sec - time.time() % frequency_sleep_sec)


class SensorImpl:
    def __init__(self, out_dir: str):
        self.process = psutil.Process(os.getpid())
        self.out_dir = out_dir

    def read_system(self) -> Dict[str, Any]:
        cpu_times_percent = psutil.cpu_times_percent()
        loadavg = psutil.getloadavg()
        state = {
            "system_cpu_percent": psutil.cpu_percent(),
            "system_cpu_times_percent_system": cpu_times_percent.system,
            "system_cpu_times_percent_user": cpu_times_percent.user,
            "system_cpu_times_percent_idle": cpu_times_percent.idle,
            "system_cpu_temp": 0,
            "system_loadavg_1": loadavg[0],
            "system_loadavg_5": loadavg[1],
            "system_loadavg_15": loadavg[2],
            "system_virtual_memory_percent": psutil.virtual_memory().percent,
        }
        return state

    def read_process(self) -> Dict[str, Any]:
        with self.process.oneshot():
            return {
                "process_cpu_percent": self.process.cpu_percent(),
                "process_cpu_time_system": self.process.cpu_times().system,
                "process_cpu_time_user": self.process.cpu_times().user,
                "process_mem_rss_percent": self.process.memory_percent(memtype="rss"),
                "process_mem_vms_percent": self.process.memory_percent(memtype="vms"),
            }

    def read_disk(self) -> Dict[str, Any]:
        output_part = self._find_mount_point(self.out_dir)
        try:
            _, _, _, percent = psutil.disk_usage(output_part)
            return {"disk_percent": percent}
        except PermissionError as e:
            logging.debug(f"Exception accessing {output_part}: {e}")
            return {"disk_percent": 0}

    def _find_mount_point(self, path: str) -> str:
        """Based on https://stackoverflow.com/a/4453715."""
        mount_point = os.path.abspath(path)
        while not os.path.ismount(mount_point):
            mount_point = os.path.dirname(mount_point)
        return mount_point


class SensorImplRaspi(SensorImpl):
    def __init__(self, out_dir: str):
        super().__init__(out_dir)

    def read_system(self) -> Dict[str, Any]:
        def get_cpu_temp():
            # TODO: better error handling
            # TODO: handle SIGNINT, e.g.: subprocess.CalledProcessError: Command 'vcgencmd measure_temp' died with <Signals.SIGINT: 2>
            return float(subprocess.check_output("vcgencmd measure_temp", shell=True).decode("utf-8").split("=")[1].split("\'")[0])

        state = super().read_system()
        state["system_cpu_temp"] = get_cpu_temp()
        return state


class Output(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.fpath = os.path.join(self.out_dir, self.options["output"])
        self.fd = None
        self.header_written = False
        self.data = []

    def _start_impl(self):
        self.fd = open(self.fpath, "w", newline="")
        self.header_written = False
        self.data = []

    def _stop_impl(self):
        self.flush()

        if self.fd:
            self.fd.close()
            self.fd = None

    def on_process_message(self, msg: base.Message):
        new_data = {"timestamp": msg.timestamp}
        new_data.update(msg.data)
        self.data.append(new_data)

        # Write data to disk every X entries
        if len(self.data) % self.options["output_write_threshold"] == 0:
            self.flush()

    def flush(self):
        if self.fd and self.data:
            writer = csv.DictWriter(self.fd, fieldnames=self.data[0].keys())
            if not self.header_written:
                writer.writeheader()
                self.header_written = True
            writer.writerows(self.data)
        self.data.clear()
        logging.info("System info output flushed")
