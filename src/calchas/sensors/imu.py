import csv
import datetime
import logging
import math
import os
import threading
import time
from typing import Any, Dict, List

import smbus2

from calchas.common import base


class Sensor(base.Publisher):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.impl = None
        self.read_thread = None
        self.request_stop = False

    def offer(self) -> List[str]:
        # TODO: support topics, e.g. gyro, acc, rot
        return ["all"]

    def _start_impl(self):
        if not self.impl:
            self.impl = smbus2.SMBus(self.options["i2c_bus"])
            self.impl.write_byte_data(self.options["address"], self.options["power_mgmt_1"], 0)

        self.request_stop = False
        if not self.read_thread:
            logging.info("Starting IMU thread...")
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"IMU thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

    def _read_thread_fn(self):
        def read_word(bus, address, reg):
            h = bus.read_byte_data(address, reg)
            l = bus.read_byte_data(address, reg + 1)
            val = (h << 8) + l
            return -((65535 - val) + 1) if (val >= 0x8000) else val

        def dist(a, b):
            return math.sqrt((a * a) + (b * b))

        address = self.options["address"]
        frequency_sleep_sec = 1. / self.options.get("frequency", 1.)
        while not self.request_stop:
            gyro_x = read_word(self.impl, address, 0x43) / 131.
            gyro_y = read_word(self.impl, address, 0x45) / 131.
            gyro_z = read_word(self.impl, address, 0x47) / 131.

            acc_x = read_word(self.impl, address, 0x3b) / 16384.
            acc_y = read_word(self.impl, address, 0x3d) / 16384.
            acc_z = read_word(self.impl, address, 0x3f) / 16384.

            rot_x = math.degrees(math.atan2(acc_x, dist(acc_y, acc_z)))
            rot_y = -math.degrees(math.atan2(acc_y, dist(acc_x, acc_z)))

            data = {
                "gyro_x": gyro_x,
                "gyro_y": gyro_y,
                "gyro_z": gyro_z,
                "acc_x": acc_x,
                "acc_y": acc_y,
                "acc_z": acc_z,
                "rot_x": rot_x,
                "rot_y": rot_y,
            }

            # TODO: create classes for payload-types
            self.publish("all", data)

            time.sleep(frequency_sleep_sec - time.time() % frequency_sleep_sec)


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
        logging.info("IMU output flushed")
