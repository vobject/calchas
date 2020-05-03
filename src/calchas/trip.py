import datetime
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List

from calchas import utils


class Trip:
    TRIP_OPTIONS_VERSION = "1.0.0"
    TRIP_OPTIONS_FILE = "trip_options.json"

    def __init__(self, parent_dir=".", mode="r", options: Dict[str, Any]=None, remove_on_exit=False, max_retries=999):
        self.parent_dir = parent_dir
        self.mode = mode
        self.remove_on_exit = remove_on_exit
        self._max_retries = max_retries

        self.options = utils.dict_merge(self.default_options(), options)
        self.directory = None

    def __enter__(self):
        if self.mode in ("r", "a"):
            self.directory = os.path.abspath(self.parent_dir)
            self.parent_dir = os.path.basename(self.directory)
            with open(os.path.join(self.directory, Trip.TRIP_OPTIONS_FILE), "r") as f:
                self.options = json.load(f)
            logging.debug(f"Trip directory opened: {self.directory}")
        elif self.mode == "w":
            dirs_tried = []
            while len(dirs_tried) <= self._max_retries:
                trip_dir_name = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
                if dirs_tried:
                    trip_dir_name += f"_{len(dirs_tried)}"
                try:
                    trip_dir = os.path.abspath(os.path.join(self.parent_dir, trip_dir_name))
                    os.makedirs(trip_dir)
                    self.directory = trip_dir
                    with open(os.path.join(self.directory, Trip.TRIP_OPTIONS_FILE), "w") as f:
                        json.dump(self.options, f, indent=4)
                    logging.info(f"Trip directory created: {self.directory}")
                    break
                except FileExistsError:
                    dirs_tried.append(trip_dir_name)
            else:
                raise FileExistsError("Unable to create trip directory.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.remove_on_exit:
            logging.info(f"Cleaning up trip directory: {self.directory}")
            shutil.rmtree(self.directory)

    def default_options(self):
        return {
            "trip": {
                "version": Trip.TRIP_OPTIONS_VERSION,
            },
            "monitors": {
                "healthmon": {
                    "name": "healthmon",
                    "active": False,
                    "dry-run": False,
                    "frequency": 1,  # Check system health once per second
                    "disk_usage_threshold": 95.0,  # Shut down when <5% disk space is available
                    "temperature_threshold": 80.0,  # Shut down when temperature is too high
                    # TODO: monitor under-voltage: https://raspberrypi.stackexchange.com/questions/60593/how-raspbian-detects-under-voltage
                },
                "display": {
                    "name": "sdd1306",
                    "active": False,
                    "dry-run": False,
                    "port": 1,
                    "address": 0x3c,
                    "rotation": 0,  # 0==0°, 1==90°, 2==180°, 3==270° clockwise
                    "width": 128,
                    "height": 64,
                    "framerate": 1,
                    "gpio_pin_prev": 17,
                    "gpio_pin_next": 27,
                    "gpio_pin_mode": 18,
                    "screens": [],
                },
            },
            "sensors": {
                "systeminfo": {
                    "name": "systeminfo",
                    "active": False,
                    "dry-run": False,
                    "frequency": 2,
                    "output": "systeminfo.csv",
                    "output_write_threshold": 20,
                },
                "picam": {
                    "name": "picam",
                    "active": False,
                    "dry-run": False,
                    "output_data": "picam.h264",
                    "output_metadata": "picam.csv",
                    "output_metadata_threshold": 300,
                    "width": 1920,
                    "height": 1080,
                    "rotation": 0,
                    "framerate": 10,
                    "format": "h264",
                    "quality": 25,
                    "init_sec": 1.,
                },
                "webcam": {
                    "name": "webcam",
                    "active": False,
                    "dry-run": False,
                    "device": 1,  # device used for cv2.VideoCapture()
                    "width": 1280,
                    "height": 720,
                    "rotation": 0,
                    "framerate": 10,
                    "format": "MJPG",  # uses a lot of cpu (on RasPi)
                    # "format": "XVID",  # leaks memory like crazy (on RasPi)
                    # "format": "mp4v",
                    "output_data": "webcam0.avi",
                    "output_metadata": "webcam0.csv",
                    "output_metadata_threshold": 300,
                },
                "imu": {
                    "name": "imu",
                    "active": False,
                    "dry-run": False,
                    "frequency": 5,
                    "output": "imu.csv",
                    "output_write_threshold": 200,
                    "i2c_bus": 1,
                    "address": 0x69,
                    "power_mgmt_1": 0x6b,
                },
                "gps": {
                    "name": "gps",
                    "active": False,
                    "dry-run": False,
                    "output": "gps.csv",
                    "output_write_threshold": 10,
                    "serial_dev": "/dev/ttyAMA0",
                    "serial_baudrate": 9600,
                    "serial_timeout": 1.,
                },
            },
        }


class TripManager:
    # Based on https://stackoverflow.com/a/48881514/53911
    _trip_regex = r"^(-?(?:[1-9][0-9]*)?[0-9]{4})(1[0-2]|0[1-9])(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9])([0-5][0-9])([0-5][0-9])(\.[0-9]+)?Z$"
    _re_match_iso8601 = re.compile(_trip_regex).match

    @staticmethod
    def is_trip_name(path: str) -> bool:
        return TripManager._re_match_iso8601(os.path.basename(path))

    @staticmethod
    def is_trip_dir(path: str) -> bool:
        return os.path.isdir(path) and TripManager.is_trip_name(os.path.basename(path))

    @staticmethod
    def list(parent_dir: str=".") -> List[str]:
        if os.path.isdir(parent_dir) is False:
            raise ValueError(f"{parent_dir} is not a directory")
        return [os.path.abspath(os.path.join(parent_dir, p)) for p in os.listdir(parent_dir) if TripManager.is_trip_dir(os.path.join(parent_dir, p))]

    @staticmethod
    def cleanup(parent_dir: str=".") -> None:
        for td in TripManager.list(parent_dir):
            shutil.rmtree(td)

    @staticmethod
    def new(parent_dir=".", options: Dict[str, Any]=None, remove_on_exit=False) -> Trip:
        return Trip(parent_dir, mode="w", options=options, remove_on_exit=remove_on_exit)

    @staticmethod
    def append(trip_dir=".", remove_on_exit=False) -> Trip:
        return Trip(trip_dir, mode="r", remove_on_exit=remove_on_exit)

    @staticmethod
    def read(trip_dir=".") -> Trip:
        return Trip(trip_dir, mode="r")


def main():
    """Test utility for the local classes."""
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    with TripManager.read("./20200417T170614Z") as trip:
        print(trip.directory)
        print(trip.options)

    print("trips: ", TripManager.list())
    #TripManager.cleanup()


if __name__ == "__main__":
    main()
