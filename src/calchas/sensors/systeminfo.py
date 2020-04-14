import csv
import datetime
import logging
import os
import platform
import subprocess
import threading
import time
from typing import Any, Dict

import psutil

from calchas import monitor
from calchas.sensors import base


class SystemInfo(base.MonitoredSensor):
    def __init__(self, options: Dict[str, Any], healthmon: monitor.HealthMonitor):
        super().__init__(options, healthmon)

        self.impl = None
        self.output = None
        self.read_thread = None
        self.request_stop = False

        if not self.dry_run:
            if platform.system() == "Windows":
                self.impl = SystemInfoWindowsImpl()
            elif platform.system() == "Linux" and os.uname()[4][:3] == "arm":  # TODO: identify raspberry pi
                self.impl = SystemInfoRaspiImpl()
            else:
                # Generic implementation
                self.impl = SystemInfoImpl()

    def _start_impl(self):
        if not self.dry_run and not self.output:
            logging.info("Setting up system info output files...")
            self.output = SystemInfoOutput(self.out_dir)
            logging.info(f"System info output files done: {self.output}")

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
        if self.output:
            self.output.close()
            self.output = None

    def _read_thread_fn(self):
        while not self.request_stop:
            sysinfo = {
                "timestamp": int(time.time() * 1000),
                "filesystem": {} if self.dry_run else self.impl.read_fs(),
                "process": {} if self.dry_run else self.impl.read_process(),
                "temperature": {} if self.dry_run else self.impl.read_temp(),
            }

            self.monitor(sysinfo)

            if self.output:
                self.output.write(sysinfo)

            time.sleep(.9)


class SystemInfoImpl:
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


class SystemInfoWindowsImpl(SystemInfoImpl):
    pass


class SystemInfoRaspiImpl(SystemInfoImpl):
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


class SystemInfoOutput():
    def __init__(self, out_dir: str, fname="systeminfo.csv", write_threshold: int=10):
        super().__init__()

        self.fpath = os.path.join(out_dir, fname)
        self.fd = open(self.fpath, "w", newline="")
        self.request_stop = False

        self.header_written = False
        self.data = []
        self.data_threshold = write_threshold

    def __repr__(self):
        return f"sysinfo_cache={len(self.data)}/{self.data_threshold} path={self.fpath}"

    def __str__(self):
        return self.__repr__()

    def write(self, data: Dict[str, Any]):
        if self.request_stop:
            return

        self.data.append(
            [
                data["timestamp"],
                data["process"]["cpu_percent"],
                data["process"]["mem_rss"],
                data["process"]["mem_vms"],
                #data["filesystem"]["/"]["percent"],
                #data["temperature"]["cpu"],
                #data["temperature"]["gpu"],
            ]
        )

        # Write gps data to disk every X entries
        if len(self.data) % self.data_threshold == 0:
            self.flush()

    def flush(self):
        if self.fd:
            writer = csv.writer(self.fd)
            if not self.header_written:
                writer.writerow(["timestamp", "process_cpu", "process_rss", "process_vms", "disk_used", "temp_cpu", "temp_gpu"])
                self.header_written = True
            writer.writerows(self.data)
        self.data.clear()
        logging.info("System info output flushed")

    def close(self):
        self.request_stop = True

        self.flush()

        if self.fd:
            self.fd.close()
            self.fd = None
