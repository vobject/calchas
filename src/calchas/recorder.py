import importlib
import logging
from typing import Any, Dict, List, Tuple

from calchas import trip, utils
from calchas.common import base


class Recorder:
    def __init__(self, trip: trip.Trip):
        super().__init__()

        self.trip = trip
        self.monitors: List[base.Subscriber] = []
        self.sensors: List[Tuple[base.Publisher, base.Subscriber]] = []
        self.running = False

    def start(self):
        if self.running:
            logging.warning("Trying to start a recorder that is already running")
            return
        logging.info("Starting Recorder")
        self._start_monitors()
        self._start_sensors()
        self.running = True
        logging.info("Data recording started")

    def stop(self):
        if not self.running:
            logging.warning("Trying to stop a recorder that is not running")
            return
        logging.info("Stopping Recorder")
        self._stop_sensors()
        self._stop_monitors()
        self.running = False
        logging.info("Data recording stopped")

    def _start_monitors(self):
        monitors = []
        for name, options in self.trip.options.get("monitors", {}).items():
            if options.get("active", False):
                monitors.append(self._create_monitor_instance(name, options))
        for mon in monitors:
            logging.info(f"Starting {mon.name}...")
            if not mon.start():
                logging.error(f"Failed to start {mon.name}")
                continue

            # TODO: handles this using healthmon options
            if mon.name == "healthmon":
                mon.register_shutdown_callback(self.stop)

            self.monitors.append(mon)
            logging.info(f"{mon.name} started.")

    def _stop_monitors(self):
        for mon in reversed(self.monitors):
            logging.info(f"Stopping {mon.name}...")
            mon.stop()
            logging.info(f"{mon.name} stopped.")
        self.monitors = []

    def _start_sensors(self):
        sensors: Tuple[base.Publisher, base.Subscriber] = []
        for name, options in self.trip.options.get("sensors", {}).items():
            if options.get("active", False):
                sensors.append(self._create_sensor_instance(name, options))
        for pub, sub in sensors:
            logging.info(f"Starting {pub.name}...")
            for mon in self.monitors:
                pub.subscribe(mon)

            if sub:
                pub.subscribe(sub)
                if not sub.start():
                    logging.error(f"Failed to start {sub.name}")
                    pub.unsubscribe(sub)
                    for mon in reversed(self.monitors):
                        pub.unsubscribe(mon)
                    continue

            if not pub.start():
                logging.error(f"Failed to start {pub.name}")
                if sub:
                    pub.unsubscribe(sub)
                    sub.stop()
                for mon in reversed(self.monitors):
                    pub.unsubscribe(mon)
                continue

            self.sensors.append((pub, sub))
            logging.info(f"{pub.name} started.")

    def _stop_sensors(self):
        for pub, sub in reversed(self.sensors):
            logging.info(f"Stopping {pub.name}...")
            pub.stop()
            if sub:
                pub.unsubscribe(sub)
                sub.stop()
            for mon in reversed(self.monitors):
                pub.unsubscribe(mon)
            logging.info(f"{pub.name} stopped.")
        self.sensors = []

    def _create_monitor_instance(self, name: str, options: Dict[str, Any]) -> base.Subscriber:
        logging.info(f"Loading {name}...")
        options = utils.dict_merge(options.copy(), { "out_dir": self.trip.directory })
        module = importlib.import_module(f"calchas.monitors.{name}")
        return module.Monitor(options)

    def _create_sensor_instance(self, name: str, options: Dict[str, Any]) -> Tuple[base.Publisher, base.Subscriber]:
        logging.info(f"Loading {name}...")
        options = utils.dict_merge(options.copy(), { "out_dir": self.trip.directory })
        module = importlib.import_module(f"calchas.sensors.{name}")
        pub = module.Sensor(options)
        sub = module.Output(options) if options.get("dry-run", False) is False else None
        return pub, sub
