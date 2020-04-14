import csv
import datetime
import io
import logging
import os
import threading
import time
from typing import Any, Dict

import picamera
import PIL

from calchas import monitor
from calchas.sensors import base


class PiCamera(base.MonitoredSensor):
    def __init__(self, options: Dict[str, Any], healthmon: monitor.HealthMonitor):
        super().__init__(options, healthmon)

        self.output = None
        self.camera = None

        # TODO: rework preview logic/handling and in stop()
        self.lastpreviewimg = time.time()
        self.previewimage = None

    def _start_impl(self):
        if not self.dry_run and not self.output:
            logging.info("Setting up camera output files...")
            self.output = CameraOutput(self.out_dir)
            logging.info(f"Camera output files done: {self.output}")

        if not self.camera:
            logging.info("Setting up camera...")
            try:
                self.camera = picamera.PiCamera()
            except picamera.exc.PiCameraError as ex:
                logging.error(f"Failed to set up camera. Error: {ex}")
                # TODO: report to monitoring
                self.stop()
                return
            self.camera.resolution = (self.options["width"], self.options["height"])
            self.camera.framerate = self.options["framerate"]
            self.camera.rotation = self.options["rotation"]
            time.sleep(self.options["init_sec"])
            logging.info(f"Camera setup done: {self.camera}")

            self.camera.start_preview()
            self.camera.start_recording(self, format=self.options["format"], quality=self.options["quality"])

    def _stop_impl(self):
        if self.camera:
            self.camera.stop_recording()
            self.camera.close()
            self.camera = None
        if self.output:
            self.output.close()
            self.output = None

    def write(self, image):
        current_time = time.time()
        if current_time - self.lastpreviewimg >= .5:
            stream = io.BytesIO()
            self.camera.capture(stream, use_video_port=True, format="jpeg", resize=(320,200))
            stream.seek(0)
            self.previewimage = PIL.Image.open(stream)
            self.lastpreviewimg = current_time

        self.monitor({"frame":self.camera.frame, "image":image, "preview":self.previewimage})
        self.output.write(self.camera.frame, image)

    def flush(self):
        pass


class CameraOutput:
    def __init__(self, out_dir: str, data_name="picamera.h264", metadata_name="picamera.csv", metadata_threshold: int=100):
        super().__init__()

        self.data_path = os.path.join(out_dir, data_name)
        self.metadata_path = os.path.join(out_dir, metadata_name)

        self.data_fd = open(self.data_path, "wb")
        self.metadata_fd = open(self.metadata_path, "w")
        self.request_stop = False

        self.frame_cnt = 0
        self.incomplete_frames = []
        self.metadata_header_written = False
        self.metadata = []
        self.metadata_threshold = metadata_threshold

    def __repr__(self):
        return f"frames={self.frame_cnt} metadata_cache={len(self.metadata)}/{self.metadata_threshold} data={self.data_path} metadata={self.metadata_path}"

    def __str__(self):
        return self.__repr__()

    def write(self, frame, image):
        if self.request_stop:
            return

        timestamp = int(time.time() * 1000)

        # Always write data
        self.data_fd.write(image)

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

        #logging.debug(f"frame {frame} ts={timestamp}")

        self.metadata.append(
            [
                timestamp,
                self.frame_cnt - 1,
                frame.frame_type,
                frame_size,
                frame.video_size,
            ]
        )

        # Write meta data to disk every X entries
        if len(self.metadata) % self.metadata_threshold == 0:
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

    def close(self):
        self.request_stop = True

        self.flush()

        if self.data_fd:
            self.data_fd.close()
            self.data_fd = None

        if self.metadata_fd:
            self.metadata_fd.close()
            self.metadata_fd = None
