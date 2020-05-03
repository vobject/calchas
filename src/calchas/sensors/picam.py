import csv
import datetime
import io
import logging
import os
import threading
import time
from typing import Any, Dict, List

import picamera
from PIL import Image

from calchas.common import base


class Sensor(base.Publisher):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.impl = None

        # TODO: rework preview logic/handling and in stop()
        self.lastpreviewimg = time.time()
        self.previewimage = None

    def offer(self) -> List[str]:
        # TODO: support topics
        return ["all"]

    def _start_impl(self):
        if not self.impl:
            logging.info("Setting up camera...")
            self.impl = picamera.PiCamera()
            self.impl.resolution = (self.options["width"], self.options["height"])
            self.impl.framerate = self.options["framerate"]
            self.impl.rotation = self.options["rotation"]

            # Turn off camera LED; only works when running as root.
            # Alternatively, set 'disable_camera_led=1' in /boot/config.txt.
            self.impl.led = False

            time.sleep(self.options["init_sec"])
            logging.info(f"Camera setup done: {self.impl}")

            if self.dry_run:
                self.impl.start_preview()
                self.impl.preview.alpha = 128
            self.impl.start_recording(self, format=self.options["format"], quality=self.options["quality"])

    def _stop_impl(self):
        if self.impl:
            if self.dry_run:
                self.impl.stop_preview()
            self.impl.stop_recording()
            self.impl.close()
            self.impl = None

    def write(self, image):
        current_time = time.time()
        if current_time - self.lastpreviewimg >= .5:
            stream = io.BytesIO()
            self.impl.capture(stream, use_video_port=True, format="jpeg", resize=(320,200))
            stream.seek(0)
            self.previewimage = Image.open(stream)
            self.lastpreviewimg = current_time

        data = {
            "frame": self.impl.frame,
            "image": image,
            "preview": self.previewimage,
        }

        # TODO: create classes for payload-types
        self.publish("all", data)


class Output(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)

        self.data_path = os.path.join(self.out_dir, self.options["output_data"])
        self.metadata_path = os.path.join(self.out_dir, self.options["output_metadata"])

        self.data_fd = None
        self.metadata_fd = None

        self.frame_cnt = 0
        self.incomplete_frames = []
        self.metadata_header_written = False
        self.metadata = []

    def _start_impl(self):
        self.data_fd = open(self.data_path, "wb")
        self.metadata_fd = open(self.metadata_path, "w")

        self.frame_cnt = 0
        self.incomplete_frames = []
        self.metadata_header_written = False
        self.metadata = []

    def _stop_impl(self):
        self.flush()

        if self.data_fd:
            self.data_fd.close()
            self.data_fd = None

        if self.metadata_fd:
            self.metadata_fd.close()
            self.metadata_fd = None

    def on_process_message(self, msg: base.Message):
        # Always write data
        self.data_fd.write(msg.data["image"])

        timestamp = msg.timestamp
        frame = msg.data["frame"]

        if frame.complete is False:
            self.incomplete_frames.append((timestamp, frame))
            return

        self.frame_cnt += 1
        frame_size = frame.frame_size

        if self.incomplete_frames:
            # Use the timestamp of the first frame message
            timestamp = self.incomplete_frames[0][0]

            # Consider the size of the previous incomplete frames
            for incomplete_frame in self.incomplete_frames:
                frame_size += incomplete_frame[1].frame_size

            self.incomplete_frames.clear()

        self.metadata.append([
            timestamp,
            self.frame_cnt - 1,
            frame.frame_type,
            frame_size,
            frame.video_size,
        ])

        # Write meta data to disk every X entries
        if len(self.metadata) % self.options["output_metadata_threshold"] == 0:
            self.flush()

    def flush(self):
        if self.metadata_fd:
            writer = csv.writer(self.metadata_fd)
            if not self.metadata_header_written:
                writer.writerow(["timestamp", "frame_num", "frame_type", "frame_size", "video_size"])
                self.metadata_header_written = True
            writer.writerows(self.metadata)
        self.metadata.clear()
        logging.info("PiCamera metadata output flushed")
