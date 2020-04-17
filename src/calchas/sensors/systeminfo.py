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

    def _start_impl(self):
        if not self.impl:
            if platform.system() == "Windows":
                self.impl = SensorImplWindows()
            elif platform.system() == "Linux" and os.uname()[4][:3] == "arm":  # TODO: identify raspberry pi
                self.impl = SensorImplRaspi()
            else:
                # Generic implementation
                self.impl = SensorImpl()

        self.request_stop = False
        if not self.read_thread:
            logging.info("Starting system info thread...")
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"System info thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

    def _read_thread_fn(self):
        while not self.request_stop:
            data = {
                "filesystem": self.impl.read_fs(),
                "process": self.impl.read_process(),
                "temperature": self.impl.read_temp(),
            }

            # TODO: create classes for payload-types
            self.publish("all", data)

            time.sleep(.5)


class SensorImpl:
    def __init__(self):
        self.process = psutil.Process(os.getpid())

    def read_fs(self) -> Dict[str, Any]:
        state = {}
        for part in psutil.disk_partitions():
            try:
                total, used, free, percent = psutil.disk_usage(part.mountpoint)
                state[part.mountpoint] = {
                    "total": total,
                    "used": used,
                    "free": free,
                    "percent": percent,
                }
            except PermissionError as e:
                logging.debug(f"Exception accessing {part}: {e}")
        return state

    def read_process(self) -> Dict[str, Any]:
        meminfo = self.process.memory_info()
        return {
            "cpu_percent": self.process.cpu_percent(interval=.1),
            "mem_rss": meminfo.rss,
            "mem_vms": meminfo.vms,
        }

    def read_temp(self) -> Dict[str, Any]:
        return {}


class SensorImplWindows(SensorImpl):
    pass


class SensorImplRaspi(SensorImpl):
    def read_temp(self) -> Dict[str, Any]:
        def get_cpu_temp():
            return float(subprocess.check_output("vcgencmd measure_temp", shell=True).decode("utf-8").split("=")[1].split("\'")[0])
        def get_gpu_temp():
            return float(int(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1000.)

        # TODO: better error handling
        # TODO: handle SIGNINT, e.g.: subprocess.CalledProcessError: Command 'vcgencmd measure_temp' died with <Signals.SIGINT: 2>
        return {
            "cpu": get_cpu_temp(),
            "gpu": get_gpu_temp(),
        }


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
        self.data.append([
            msg.timestamp,
            msg.data["process"]["cpu_percent"],
            msg.data["process"]["mem_rss"],
            msg.data["process"]["mem_vms"],
            msg.data["filesystem"]["/"]["percent"],
            msg.data["temperature"]["cpu"],
            msg.data["temperature"]["gpu"],
        ])

        # Write data to disk every X entries
        if len(self.data) % self.options["output_write_threshold"] == 0:
            self.flush()

    def flush(self):
        if self.fd and (self.data or not self.header_written):
            writer = csv.writer(self.fd)
            if not self.header_written:
                writer.writerow(["timestamp", "process_cpu", "process_rss", "process_vms", "disk_used", "temp_cpu", "temp_gpu"])
                self.header_written = True
            writer.writerows(self.data)
        self.data.clear()
        logging.info("System info output flushed")
