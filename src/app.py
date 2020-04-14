#!/usr/bin/env python3

import argparse
import datetime
import logging
import platform
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

from calchas import monitor, recorder, trip


def main():
    logging.info("Starting program")
    try:
        trip_options = {
            "systeminfo": { "active": True },
            "picamera": { "active": False },
            "webcam": { "active": False },
            "imu": { "active": False },
            "gps": {
                "active": False,
                "serial_dev": "COM4" if platform.system() == "Windows" else "/dev/ttyAMA0",
            },
        }
        with trip.TripManager.new(".", True, trip_options) as new_trip:
            with monitor.HealthMonitor(new_trip) as new_monitor:
                rec = recorder.Recorder(new_trip, new_monitor)

                new_monitor.register_shutdown_callback(lambda: rec.stop())

                rec.start()
                while rec.running:
                    time.sleep(1.)
    except Exception:
        logging.exception("Something went wrong")
    logging.info("Exiting program")


if __name__ == "__main__":
    main()
