#!/usr/bin/env python3

import argparse
import enum
import logging
import os
import platform
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

import gpiozero

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, "src")))

from calchas import monitor, recorder, trip


class StartupFlags(enum.Enum):
    """GPIO pins are connected to dip switches and control how the program runs."""
    RECORDER = gpiozero.Button(12, bounce_time=.1)
    DISPLAY = gpiozero.Button(6, bounce_time=.1)

    SENSOR_SYSINFO = gpiozero.Button(13, bounce_time=.1)
    SENSOR_PICAM = gpiozero.Button(19, bounce_time=.1)
    SENSOR_WEBCAM = gpiozero.Button(16, bounce_time=.1)
    SENSOR_IMU = gpiozero.Button(20, bounce_time=.1)
    SENSOR_GPS = gpiozero.Button(26, bounce_time=.1)

    UNUSED_21 = gpiozero.Button(21, bounce_time=.1)

    def is_active(self) -> bool:
        return self.value.is_pressed

    @classmethod
    def log_state(cls):
        print("StartupFlags:")
        for f in StartupFlags:
            print(f"    flag={f.name} pin={f.value.pin} active={f.value.is_pressed}")


class ControlButtons(enum.Enum):
    """Button actions during runtime."""
    STOP_CALCHAS = gpiozero.Button(25, hold_time=2.)

    # MENU_PREV = gpiozero.Button(17, bounce_time=.1)
    # MENU_NEXT = gpiozero.Button(27, bounce_time=.1)
    # MENU_MODE = gpiozero.Button(18, bounce_time=.1)

    def when_held(self, callback):
        self.value.when_held = callback


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("trips_dir", help="The directory to save recorded trip data.")
    parser.add_argument("-f", "--force", action="store_true", help="Ignore the recorder startup pin.")
    parser.add_argument("-n", "--temporary", action="store_true", help="Remove the trip directory when exiting.")

    return parser.parse_args()


def main() -> int:
    # TODO: Allow overriding StartupFlags with commandline arguments.
    args = parse_args()

    if not args.force and not StartupFlags.RECORDER.is_active():
        logging.info("Recorder flag is inactive. Exiting.")
        return 0

    logging.info("Starting program")
    StartupFlags.log_state()

    trip_options = {
        "sensors": {
            "systeminfo": {
                "active": StartupFlags.SENSOR_SYSINFO.is_active(),
            },
            "picam": {
                "active": StartupFlags.SENSOR_PICAM.is_active(),
            },
            "webcam": {
                "active": StartupFlags.SENSOR_WEBCAM.is_active(),
                "dry-run": False,
                "device": 0,
                "format": "mp4v",
                "width": 640,
                "height": 480,
            },
            "imu": {
                "active": StartupFlags.SENSOR_IMU.is_active(),
            },
            "gps": {
                "active": StartupFlags.SENSOR_GPS.is_active(),
                "serial_dev": "COM4" if platform.system() == "Windows" else "/dev/ttyAMA0",
            },
        },
    }

    try:
        with trip.TripManager.new(args.trips_dir, trip_options, remove_on_exit=args.temporary) as new_trip:
            with monitor.HealthMonitor(new_trip) as new_monitor:
                # with vis.Menu(new_trip, new_monitor, ControlButtons.MENU_PREV, ControlButtons.MENU_NEXT, ControlButtons.MENU_MODE) as ui:
                rec = recorder.Recorder(new_trip, new_monitor)

                ControlButtons.STOP_CALCHAS.when_held(lambda: rec.stop())

                rec.start()
                while rec.running:
                    time.sleep(1.)
        rc = 0
    except Exception:
        logging.exception("Something went wrong")
        rc = 1

    logging.info(f"Exiting program (rc={rc})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
