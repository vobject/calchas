import datetime
import logging
import os
import re
import shutil
from typing import Any, Dict, List

from calchas import utils


class Trip:
    def __init__(self, parent_dir=".", mode="r", temporary=False, options: Dict[str, Any]=None, max_retries=999):
        self.parent_dir = parent_dir
        self.mode = mode
        self.temporary = temporary
        self._max_retries = max_retries

        self.options = utils.dict_merge(self.default_options(), options)
        self.directory = None

    def __enter__(self):
        if self.mode in ("r", "a"):
            self.directory = os.path.abspath(self.parent_dir)
            self.parent_dir = os.path.basename(self.directory)
            logging.info(f"Trip directory opened: {self.directory}")
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
                    logging.info(f"Trip directory created: {self.directory}")
                    break
                except FileExistsError:
                    dirs_tried.append(trip_dir_name)
            else:
                raise FileExistsError("Unable to create trip directory.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temporary:
            logging.info(f"Cleaning up trip directory: {self.directory}")
            shutil.rmtree(self.directory)

    def default_options(self):
        return {
            "systeminfo": {
                "name": "systeminfo",
                "active": False,
                "dry-run": False,
            },
            "picamera": {
                "name": "picamera",
                "active": False,
                "dry-run": False,
                "width": 1920,
                "height": 1080,
                "rotation": 0,
                "framerate": 10,
                "format": "h264",
                "quality": 25,
                "init_sec": 2,
            },
            "webcam": {
                "name": "webcam0",
                "active": False,
                "dry-run": False,
                "device": 0,
                "width": 640,
                "height": 480,
                "rotation": 0,
                "framerate": 10,
            },
            "imu": {
                "name": "imu",
                "active": False,
                "dry-run": False,
                "i2c_bus": 1,
                "address": 0x68,
                "power_mgmt_1": 0x6b,
            },
            "gps": {
                "name": "gps",
                "active": False,
                "dry-run": False,
                "serial_dev": "/dev/ttyAMA0",
                "serial_baudrate": 9600,
                "serial_timeout": 1.,
            },
        }


class TripManager:
    # Based on https://stackoverflow.com/a/48881514/53911
    _trip_regex = r"^(-?(?:[1-9][0-9]*)?[0-9]{4})(1[0-2]|0[1-9])(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9])([0-5][0-9])([0-5][0-9])(\.[0-9]+)?Z$"
    _re_match_iso8601 = re.compile(_trip_regex).match

    @staticmethod
    def is_trip_dir(path: str) -> bool:
        return os.path.isdir(path) and TripManager._re_match_iso8601(os.path.basename(path))

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
    def new(parent_dir=".", temporary=False, options: Dict[str, Any]=None) -> Trip:
        return Trip(parent_dir, mode="w", temporary=temporary, options=options)

    @staticmethod
    def append(trip_dir=".", temporary=False) -> Trip:
        return Trip(trip_dir, mode="r", temporary=temporary)

    @staticmethod
    def read(trip_dir=".") -> Trip:
        return Trip(trip_dir, mode="r")


def main():
    """Test utility for the local classes."""
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
    with TripManager.append(".", temporary=True) as trip:
        print(trip.directory)

        print("trips: ", TripManager.list())
    TripManager.cleanup()


if __name__ == "__main__":
    main()
