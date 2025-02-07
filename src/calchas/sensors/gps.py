import csv
import datetime
import logging
import os
import threading
import time
from typing import Any, Dict, List

import pynmea2
import serial

from calchas.common import base


class NMEAByteStream:
    def __init__(self, stream):
        self.stream = stream

    def readline(self):
        while True:
            try:
                begin = self._read_to_begin()
                rest = self._read_until_end()
                return (begin + rest).decode("ascii")
            except UnicodeDecodeError as ex:
                logging.warning(f"Failed reading from byte stream: {ex}. Retrying...")

    def _read_to_begin(self):
        while True:
            c = self.stream.read(1)
            if c in (b'$', b'!'): return c

    def _read_until_end(self):
        line = bytearray()
        while True:
            c = self.stream.read(1)
            if c == b'\x00': continue
            if not c: break
            line += c
            if line[-2:] == b'\r\n': break
            if len(line) >= 81: break
        return bytes(line)


class NMEAByteStreamReader(pynmea2.NMEAStreamReader):
    def __init__(self, stream, errors="raise"):
        super().__init__(NMEAByteStream(stream), errors)


NEO_GPS_SAMPLE_RATE_CONFIGS = {
    "1Hz": [0xB5,0x62,0x06,0x08,0x06,0x00,0xE8,0x03,0x01,0x00,0x01,0x00,0x01,0x39,],
    "5Hz": [0xB5,0x62,0x06,0x08,0x06,0x00,0xC8,0x00,0x01,0x00,0x01,0x00,0xDE,0x6A,],
    "10Hz": [0xB5,0x62,0x06,0x08,0x06,0x00,0x64,0x00,0x01,0x00,0x01,0x00,0x7A,0x12,],
}


class Sensor(base.Publisher):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.serial = None
        self.read_thread = None
        self.request_stop = False

    def offer(self) -> List[str]:
        # TODO: support topics, e.g. NMEA message types
        return ["all"]

    def _start_impl(self):
        if not self.serial:
            self.serial = serial.Serial(self.options["serial_dev"], baudrate=self.options["serial_baudrate"], timeout=self.options["serial_timeout"])

            # TODO: make this configurable through trip options.
            self.serial.write(bytes(NEO_GPS_SAMPLE_RATE_CONFIGS["5Hz"]))

        self.request_stop = False
        if not self.read_thread:
            logging.info("Starting GPS thread...")
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"GPS thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

    def _read_thread_fn(self):
        if self.request_stop:
            return

        for batch in NMEAByteStreamReader(self.serial):
            if self.request_stop:
                return

            # FIXME: when there's no GPS connected, this will block indefinitely
            for msg in batch:
                if isinstance(msg, pynmea2.GGA):
                    # TODO: create classes for payload-types
                    self.publish("all", msg)

            if self.request_stop:
                return


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
            msg.data.longitude or 0.0,
            msg.data.latitude or 0.0,
            msg.data.altitude or 0.0,
        ])

        # Write data to disk every X entries
        if len(self.data) % self.options["output_write_threshold"] == 0:
            self.flush()

    def flush(self):
        if self.fd and (self.data or not self.header_written):
            writer = csv.writer(self.fd)
            if not self.header_written:
                writer.writerow(["timestamp", "longitude", "latitude", "altitude"])
                self.header_written = True
            writer.writerows(self.data)
        self.data.clear()
        logging.info("GPS output flushed")
