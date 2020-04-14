import csv
import datetime
import logging
import math
import os
import threading
import time
from typing import Any, Dict

try:
    import smbus2
except ImportError:
    logging.warning("Unable to import smbus2. This is not an issue during dry-run.")

from calchas import monitor
from calchas.sensors import base


class Imu(base.MonitoredSensor):
    def __init__(self, options: Dict[str, Any], healthmon: monitor.HealthMonitor):
        super().__init__(options, healthmon)

        self.output = None
        self.bus = None
        self.read_thread = None
        self.request_stop = False

    def _start_impl(self):
        if not self.dry_run and not self.output:
            logging.info("Setting up IMU output files...")
            self.output = ImuOutput(self.out_dir)
            logging.info(f"IMU output files done: {self.output}")

        if not self.dry_run and not self.read_thread:
            logging.info("Starting IMU thread...")
            self.bus = smbus2.SMBus(self.options["i2c_bus"])
            self.bus.write_byte_data(self.options["address"], self.options["power_mgmt_1"], 0)
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"IMU thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None
        if self.output:
            self.output.close()
            self.output = None

    def _read_thread_fn(self):
        if self.request_stop:
            return

        def read_word(bus, address, reg):
            h = bus.read_byte_data(address, reg)
            l = bus.read_byte_data(address, reg + 1)
            val = (h << 8) + l
            return -((65535 - val) + 1) if (val >= 0x8000) else val

        def dist(a, b):
            return math.sqrt((a * a) + (b * b))

        address = self.options["address"]
        while True:
            if self.request_stop:
                return

            gyro_x = read_word(self.bus, address, 0x43) / 131.
            gyro_y = read_word(self.bus, address, 0x45) / 131.
            gyro_z = read_word(self.bus, address, 0x47) / 131.

            acc_x = read_word(self.bus, address, 0x3b) / 16384.
            acc_y = read_word(self.bus, address, 0x3d) / 16384.
            acc_z = read_word(self.bus, address, 0x3f) / 16384.

            rot_x = math.degrees(math.atan2(acc_x, dist(acc_y, acc_z)))
            rot_y = -math.degrees(math.atan2(acc_y, dist(acc_x, acc_z)))

            data = {
                "timestamp": int(time.time() * 1000),
                "gyro_x": gyro_x,
                "gyro_y": gyro_y,
                "gyro_z": gyro_z,
                "acc_x": acc_x,
                "acc_y": acc_y,
                "acc_z": acc_z,
                "rot_x": rot_x,
                "rot_y": rot_y,
            }

            self.monitor(data)
            self.output.write(data)

            time.sleep(0.1)


class ImuOutput():
    def __init__(self, out_dir: str, fname="imu.csv", write_threshold: int=100):
        super().__init__()

        self.fpath = os.path.join(out_dir, fname)
        self.fd = open(self.fpath, "w", newline="")
        self.request_stop = False

        self.header_written = False
        self.data = []
        self.data_threshold = write_threshold

    def __repr__(self):
        return f"imu_cache={len(self.data)}/{self.data_threshold} path={self.fpath}"

    def __str__(self):
        return self.__repr__()

    def write(self, data: Dict[str, Any]):
        if self.request_stop:
            return

        self.data.append(data)

        # Write gps data to disk every X entries
        if len(self.data) % self.data_threshold == 0:
            self.flush()

    def flush(self):
        if self.fd and self.data:
            writer = csv.DictWriter(self.fd, fieldnames=self.data[0].keys())
            if not self.header_written:
                writer.writeheader()
                self.header_written = True
            writer.writerows(self.data)
        self.data.clear()
        logging.info("IMU output flushed")

    def close(self):
        self.request_stop = True

        self.flush()

        if self.fd:
            self.fd.close()
            self.fd = None
