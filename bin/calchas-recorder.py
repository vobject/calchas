#!/usr/bin/env python3

import argparse
import enum
import logging
import os
import platform
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, "src")))

from calchas import recorder, trip


class StartupFlags(enum.Enum):
    """GPIO pins are connected to dip switches and control how the program runs."""
    RECORDER = 12
    DISPLAY = 6

    SENSOR_SYSINFO = 13
    SENSOR_PICAM = 19
    SENSOR_WEBCAM = 16
    SENSOR_IMU = 20
    SENSOR_GPS = 26

    UNUSED_21 = 21

    def __init__(self, gpio_pin: int):
        self.gpio_pin = gpio_pin
        try:
            import gpiozero
            self.btn = gpiozero.Button(gpio_pin, bounce_time=.1)
        except ImportError:
            self.btn = None

    def is_active(self) -> bool:
        return self.btn.is_pressed if self.btn is not None else False

    @classmethod
    def log_state(cls):
        print("StartupFlags:")
        for f in StartupFlags:
            if f.btn is not None:
                print(f"    flag={f.name} pin={f.btn.pin} active={f.btn.is_pressed}")
            else:
                print(f"    flag={f.name} pin={f.gpio_pin} active=False")


class ControlButtons(enum.Enum):
    """Button actions during runtime."""
    STOP_CALCHAS = 25

    def __init__(self, gpio_pin: int):
        self.gpio_pin = gpio_pin
        try:
            import gpiozero
            self.btn = gpiozero.Button(gpio_pin, hold_time=2.)
        except ImportError:
            self.btn = None

    def when_held(self, callback):
        if self.btn is not None:
            self.btn.when_held = callback


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("trips_dir", help="The directory to save recorded trip data.")
    parser.add_argument("-f", "--force", action="store_true", help="Ignore the recorder startup pin.")
    parser.add_argument("-n", "--temporary", action="store_true", help="Remove the trip directory when exiting.")
    parser.add_argument("--display", action="store_true", help="Ignore the recorder startup pin and enable the display.")
    parser.add_argument("--systeminfo", action="store_true", help="Ignore the recorder startup pin and start systeminfo sensor.")
    parser.add_argument("--picam", action="store_true", help="Ignore the recorder startup pin and start picam sensor.")
    parser.add_argument("--webcam", action="store_true", help="Ignore the recorder startup pin and start webcam sensor.")
    parser.add_argument("--imu", action="store_true", help="Ignore the recorder startup pin and start imu sensor.")
    parser.add_argument("--gps", action="store_true", help="Ignore the recorder startup pin and start gps sensor.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.force and not StartupFlags.RECORDER.is_active():
        logging.info("Recorder flag is inactive. Exiting.")
        return 0

    logging.info("Starting program")
    StartupFlags.log_state()

    # Override a trip's default options.
    trip_options = {
        "monitors": {
            "healthmon": {
                "active": True,
            },
            "sdd1306": {
                "active": args.display or StartupFlags.DISPLAY.is_active(),
                "screens": [],
            },
        },
        "sensors": {
            "systeminfo": {
                "active": args.systeminfo or StartupFlags.SENSOR_SYSINFO.is_active(),
            },
            "picam": {
                "active": args.picam or StartupFlags.SENSOR_PICAM.is_active(),
            },
            "webcam": {
                "active": args.webcam or StartupFlags.SENSOR_WEBCAM.is_active(),
                "dry-run": False,
                "device": 0,
                "format": "mp4v",
                "width": 640,
                "height": 480,
            },
            "imu": {
                "active": args.imu or StartupFlags.SENSOR_IMU.is_active(),
            },
            "gps": {
                "active": args.gps or StartupFlags.SENSOR_GPS.is_active(),
                "serial_dev": "COM4" if platform.system() == "Windows" else "/dev/ttyAMA0",
            },
        },
    }

    # Activate display screens for active sensors.
    def activate_screen(options, sensor: str):
        if options["sensors"][sensor]["active"] is True:
            options["monitors"]["sdd1306"]["screens"].append(sensor)
    activate_screen(trip_options, "systeminfo")
    activate_screen(trip_options, "picam")
    activate_screen(trip_options, "webcam")
    activate_screen(trip_options, "imu")
    activate_screen(trip_options, "gps")

    try:
        with trip.TripManager.new(args.trips_dir, trip_options, args.temporary) as new_trip:
            rec = recorder.Recorder(new_trip)

            # TODO: add this to healthmon internal handling
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
