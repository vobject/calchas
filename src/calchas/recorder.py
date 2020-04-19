import importlib
import logging
import time
from typing import Any, Dict, List, Tuple

from calchas import monitor, trip, utils
from calchas.sensors import base


class Recorder:
    def __init__(self, trip: trip.Trip, healthmon: monitor.HealthMonitor):
        super().__init__()

        self.trip = trip
        self.healthmon = healthmon
        self.sensors: List[Tuple[base.Publisher, base.Subscriber]] = []
        self.running = False

        self.healthmon.register_shutdown_callback(self.stop)

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
        for pub, sub in self.sensors:
            logging.info(f"Starting {pub.name}...")
            pub.subscribe(self.healthmon)
            if sub:
                pub.subscribe(sub)
                sub.start()
            pub.start()
            logging.info(f"{pub.name} started.")

    def _stop_sensors(self):
        for pub, sub in reversed(self.sensors):
            logging.info(f"Stopping {pub.name}...")
            pub.stop()
            if sub:
                pub.unsubscribe(sub)
                sub.stop()
            pub.subscribe(self.healthmon)
            logging.info(f"{pub.name} stopped.")
        self.sensors = []

    def _create_sensor_instance(self, name: str, options: Dict[str, Any]) -> Tuple[base.Publisher, base.Subscriber]:
        logging.info(f"Loading {name}...")
        options = utils.dict_merge(options.copy(), { "out_dir": self.trip.directory })
        module = importlib.import_module(f"calchas.sensors.{name}")
        pub = module.Sensor(options)
        sub = module.Output(options) if options.get("dry-run", False) is False else None
        return pub, sub
