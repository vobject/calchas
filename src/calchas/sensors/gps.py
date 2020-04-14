import datetime
import logging
import os
import threading
import time
from typing import Any, Dict

import pynmea2
import serial

from calchas import monitor
from calchas.sensors import base


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
            if not c: break
            line += c
            if line[-2:] == b'\r\n': break
            if len(line) >= 81: break
        return bytes(line)


class NMEAByteStreamReader(pynmea2.NMEAStreamReader):
    def __init__(self, stream, errors="raise"):
        super().__init__(NMEAByteStream(stream), errors)


class Gps(base.MonitoredSensor):
    def __init__(self, options: Dict[str, Any], healthmon: monitor.HealthMonitor):
        super().__init__(options, healthmon)

        self.output = None
        self.serial = None
        self.read_serial_thread = None
        self.request_stop = False

    def _start_impl(self):
        if not self.dry_run and not self.output:
            logging.info("Setting up GPS output files...")
            self.output = GpsOutput(self.out_dir)
            logging.info(f"GPS output files done: {self.output}")

        if not self.dry_run and not self.serial:
            self.serial = serial.Serial(self.options["serial_dev"], baudrate=self.options["serial_baudrate"], timeout=self.options["serial_timeout"])

        if not self.dry_run and not self.read_serial_thread:
            logging.info("Starting GPS thread...")
            self.read_serial_thread = threading.Thread(target=self._read_thread_fn)
            self.read_serial_thread.start()
            logging.info(f"GPS thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_serial_thread:
            self.read_serial_thread.join()
            self.read_serial_thread = None
        if self.output:
            self.output.close()
            self.output = None

    def _read_thread_fn(self):
        if self.request_stop:
            return

        for batch in NMEAByteStreamReader(self.serial):
            if self.request_stop:
                return

            for msg in batch:
                if isinstance(msg, pynmea2.GGA):
                    self.monitor(msg)
                    self.output.write(msg)

            if self.request_stop:
                return


class GpsOutput():
    def __init__(self, out_dir: str, fname="gps.csv", write_threshold: int=100):
        super().__init__()

        self.fpath = os.path.join(out_dir, fname)
        self.fd = open(self.fpath, "w")
        self.fd.write(r"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<Style id="yellowPoly">
<LineStyle>
<color>7f00ffff</color>
<width>4</width>
</LineStyle>
<PolyStyle>
<color>7f00ff00</color>
</PolyStyle>
</Style>
<Placemark><styleUrl>#yellowPoly</styleUrl>
<LineString>
<extrude>1</extrude>
<tesselate>1</tesselate>
<altitudeMode>absolute</altitudeMode>
<coordinates>""")
        self.request_stop = False

        self.gps_positions = []
        self.gps_positions_threshold = write_threshold

    def __repr__(self):
        return f"gps_positions_cache={len(self.gps_positions)}/{self.gps_positions_threshold} path={self.fpath}"

    def __str__(self):
        return self.__repr__()

    def write(self, msg):
        if self.request_stop:
            return

        self.gps_positions.append(f"{msg.longitude},{msg.latitude},{msg.altitude}")

        # Write gps data to disk every 100 entries
        if len(self.gps_positions) % self.gps_positions_threshold == 0:
            self.flush()

    def flush(self):
        if self.fd:
            self.fd.write(" ".join(self.gps_positions))
        self.gps_positions.clear()
        logging.info("GPS output flushed")

    def close(self):
        self.request_stop = True

        self.flush()

        if self.fd:
            self.fd.write(r"""</coordinates>
</LineString></Placemark>
</Document></kml>""")
            self.fd.close()
            self.fd = None
