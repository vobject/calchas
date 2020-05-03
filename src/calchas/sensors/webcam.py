import csv
import datetime
import logging
import os
import threading
import time
from typing import Any, Dict, List

import cv2

from calchas.common import base

import io
from PIL import Image


class Sensor(base.Publisher):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.impl = None
        self.frame_cnt = 0
        self.read_thread = None
        self.request_stop = False

    def offer(self) -> List[str]:
        # TODO: support topics
        return ["all"]

    def _start_impl(self):
        if not self.impl:
            self.impl = cv2.VideoCapture(self.options["device"])
            self.impl.set(cv2.CAP_PROP_FRAME_WIDTH, self.options["width"])
            self.impl.set(cv2.CAP_PROP_FRAME_HEIGHT, self.options["height"])
            self.impl.set(cv2.CAP_PROP_FPS, self.options["framerate"])

        self.frame_cnt = 0
        self.request_stop = False
        if not self.read_thread:
            logging.info("Setting up webcam thread...")
            self.read_thread = threading.Thread(target=self._read_thread_fn)
            self.read_thread.start()
            logging.info(f"Webcam thread started.")

    def _stop_impl(self):
        self.request_stop = True
        if self.read_thread:
            self.read_thread.join()
            self.read_thread = None

        if self.impl:
            self.impl.release()
            self.impl = None

    def _read_thread_fn(self):
        while not self.request_stop:
            retval, image = self.impl.read()
            if not retval:
                logging.error(f"Failed reading image frame #{self.frame_cnt + 1} from webcam. Shutting down sensor.")
                # TODO: report error to monitoring; thow exception?
                break

            self.frame_cnt += 1
            if self.options["rotation"] == 180:
                image = cv2.rotate(image, cv2.ROTATE_180)

            data = {
                "image": image,
            }

            self.publish("all", data)


class Output(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.data_path = os.path.join(self.out_dir, self.options["output_data"])
        self.metadata_path = os.path.join(self.out_dir, self.options["output_metadata"])

        self.data_writer = None
        self.metadata_fd = None

        self.frame_cnt = 0
        self.metadata_header_written = False
        self.metadata = []

    def _start_impl(self):
        fourcc = cv2.VideoWriter_fourcc(*self.options["format"])
        self.data_writer = cv2.VideoWriter(self.data_path, fourcc, self.options["framerate"], (self.options["width"], self.options["height"]))
        self.metadata_fd = open(self.metadata_path, "w", newline="")

        self.frame_cnt = 0
        self.metadata_header_written = False
        self.metadata = []

    def _stop_impl(self):
        self.flush()

        if self.data_writer:
            self.data_writer.release()
            self.data_fd = None

        if self.metadata_fd:
            self.metadata_fd.close()
            self.metadata_fd = None

    def on_process_message(self, msg: base.Message):
        image = msg.data["image"]
        self.data_writer.write(image)

        self.frame_cnt += 1

        self.metadata.append([
            msg.timestamp,
            self.frame_cnt - 1,
            image.size,
        ])

        # Write meta data to disk every X entries
        if len(self.metadata) % self.options["output_metadata_threshold"] == 0:
            self.flush()

    def flush(self):
        if self.metadata_fd:
            writer = csv.writer(self.metadata_fd)
            if not self.metadata_header_written:
                writer.writerow(["timestamp", "frame_num", "frame_size"])
                self.metadata_header_written = True
            writer.writerows(self.metadata)
        self.metadata.clear()
        logging.info("Webcam metadata output flushed")
