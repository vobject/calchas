import logging
import time
from typing import Any, Dict

from calchas import monitor, trip, utils


class Recorder:
    def __init__(self, trip: trip.Trip, healthmon: monitor.HealthMonitor):
        super().__init__()

        self.trip = trip
        self.healthmon = healthmon
        self.sensors = []
        self.running = False

    def start(self):
        if self.running:
            logging.warning("Trying to start a recorder that is already running")
            return
        logging.info("Starting Recorder")
        self._start_sensors()
        self.running = True
        logging.info("Data recording started")

    def stop(self):
        if not self.running:
            logging.warning("Trying to stop a recorder that is not running")
            return
        logging.info("Stopping Recorder")
        self._stop_sensors()
        self.running = False
        logging.info("Data recording stopped")

    def _start_sensors(self):
        for name, options in self.trip.options.items():
            if options["active"]:
                self.sensors.append(self._create_sensor_instance(name, options))
        for sensor in self.sensors:
            logging.info(f"Starting {sensor.name}...")
            sensor.start()
            logging.info(f"{sensor.name} started.")

    def _stop_sensors(self):
        for sensor in reversed(self.sensors):
            logging.info(f"Stopping {sensor.name}...")
            sensor.stop()
            logging.info(f"{sensor.name} stopped.")
        self.sensors = []

    def _create_sensor_instance(self, name: str, options: Dict[str, Any]):
        options = utils.dict_merge(options.copy(), { "out_dir": self.trip.directory })
        logging.info(f"Loading {name}...")
        if name == "systeminfo":
            from calchas.sensors import systeminfo
            return systeminfo.SystemInfo(options, self.healthmon)
        elif name == "picamera":
            from calchas.sensors import picam
            return picam.PiCamera(options, self.healthmon)
        elif name == "webcam":
            from calchas.sensors import webcam
            return webcam.Webcam(options, self.healthmon)
        elif name == "imu":
            from calchas.sensors import imu
            return imu.Imu(options, self.healthmon)
        elif name == "gps":
            from calchas.sensors import gps
            return gps.Gps(options, self.healthmon)
        else:
            raise ValueError(f"Unknown sensor {name}")
