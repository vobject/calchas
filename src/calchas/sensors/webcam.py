import csv
import datetime
import logging
import os
import threading
import time
from typing import Any, Dict

import cv2

from calchas import monitor
from calchas.sensors import base

import io
from PIL import Image


class Webcam(base.MonitoredSensor):
    def __init__(self, options: Dict[str, Any], healthmon: monitor.HealthMonitor):
        super().__init__(options, healthmon)

        self.output = None
        self.camera = None
        self.frame_cnt = 0
        self.read_thread = None
        self.request_stop = False

    def _start_impl(self):
        if not self.dry_run and not self.output:
            logging.info("Setting up camera output files...")
            raise NotImplementedError("No camera output for Webcam class")
            self.output = None  # TODO: CameraOutput(self.out_dir)
            logging.info(f"Camera output files done: {self.output}")

        if not self.camera:
            logging.info("Setting up webcam thread...")
            self.frame_cnt = 0
            # TODO: configure camera according to options (resolution, rotation, etc.)
            self.camera = cv2.VideoCapture(self.options["device"])
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"Webcam thread started.")

    def _stop_impl(self):
        self.request_stop = True

        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

        self.camera.release()
        self.camera = None

        if self.output:
            self.output.close()
            self.output = None

    def _read_thread_fn(self):
        if self.request_stop:
            return

        while True:
            if self.request_stop:
                return

            retval, image = self.camera.read()
            if not retval:
                logging.error(f"Failed reading image frame #{self.frame_cnt + 1} from webcam. Shutting down sensor.")
                # TODO: report error to monitoring
                break

            self.frame_cnt += 1
            image = cv2.resize(image, (self.options["width"], self.options["height"]))
            if self.options["rotation"] == 180:
                image = cv2.flip(image, 0)

            self.monitor({
                "frame": {}, # TODO
                "image":image,
                "preview": image,
            })
            # self.output.write(retval, image)

            # TODO: fps control
            time.sleep(0.1)


# TODO: Webcam output class
