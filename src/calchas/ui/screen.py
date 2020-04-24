import datetime
import logging
from typing import Any, Dict, List

import PIL


import io
import numpy as np
from matplotlib import pyplot as plt
import PIL.ImageOps


def readable_bytes(num: int) -> str:
    """https://stackoverflow.com/a/52379087/53911"""
    step_unit = 1000.0

    for x in ["", "KB", "MB", "GB", "TB"]:
        if num < step_unit:
            return f"{num:.1f} {x}"
        num /= step_unit


class Base:
    def __init__(self, options: Dict[str, Any], model: Any=None):
        self.options = options
        self.model = model
        self.font = self.options.get("font", PIL.ImageFont.load_default())
        self.img = PIL.Image.new("1", (self.options["width"], self.options["height"]))
        self.img_draw = PIL.ImageDraw.Draw(self.img)

    def clear(self):
        self.img_draw.rectangle((0, 0, *self.img.size), outline=0, fill=0)
        return self.img

    def frame(self):
        return self.clear()

    def mode(self):
        pass


class SystemInfo(Base):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

        self._mode = 0
        self._modes = 2

    def frame(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        logging.info(f"SystemInfo.frame(mode={self._mode})")
        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(self.options["header"])
        self.img_draw.text(((w - header_w) / 2, top), self.options["header"], font=self.font, fill=255)

        if self.model:
            data = self.model.data
            line = 1
            if self._mode == 0:
                if data:
                    self.img_draw.text((left, top + (line * lineh)), f"SYS_CPU: {data['system_cpu_percent']}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"SYS_VM: {data['system_virtual_memory_percent']:.2f}%",  font=self.font, fill=255)
                    line += 1
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"CPU: {data['process_cpu_percent']}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"RSS: {data['process_mem_rss_percent']:.2f}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"VMS: {data['process_mem_vms_percent']:.2f}%",  font=self.font, fill=255)
                    line += 1
            if self._mode == 1:
                if data:
                    self.img_draw.text((left, top + (line * lineh)), f"DISK: {data['disk_percent']}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"TEMP CPU=:{data['system_cpu_temp']:.2f}°C",  font=self.font, fill=255)
                    line += 1
            # if self._mode == 3:
            #     # FIXME: plotting test
            #     # next 5 lines just create a matplotlib plot
            #     t = np.arange(0.0, 1.0, 0.01)
            #     s = np.sin(2 * 2 * np.pi * t)
            #     fig = plt.figure()
            #     ax1 = fig.add_subplot(111)
            #     ax1.plot(t, s)

            #     canvas = plt.get_current_fig_manager().canvas
            #     canvas.draw()
            #     pil_image = PIL.Image.frombytes("RGB", canvas.get_width_height(), canvas.tostring_rgb())
            #     pil_image = PIL.ImageOps.invert(pil_image.resize((128, 64))).convert("1")
            #     return pil_image

        return self.img

    def mode(self):
        self._mode = (self._mode + 1) % self._modes


class PiCamera(Base):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

        self._mode_idx = 0
        self._modes = [
            self._camera_stats,
            self._camera_preview,
        ]

    def frame(self):
        return self._modes[self._mode_idx]()

    def mode(self):
        self._mode_idx = (self._mode_idx + 1) % len(self._modes)

    def _camera_stats(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(self.options["header"])
        self.img_draw.text(((w - header_w) / 2, top), self.options["header"], font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"Frame Type: {self.model.data['frame'].frame_type}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Frame Complete: {self.model.data['frame'].complete}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Frame Size: {readable_bytes(self.model.data['frame'].frame_size)}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (4 * lineh)), f"Video Size: {readable_bytes(self.model.data['frame'].video_size)}",  font=self.font, fill=255)

        return self.img

    def _camera_preview(self):
        if not self.model or not self.model.data["preview"]:
            self.clear()
            return self.img

        # TODO: define what format the preview image is in
        #image = PIL.Image.open(io.BytesIO(self.model.data['preview']))
        return self.model.data["preview"].resize((128, 64)).convert("1").rotate(180)


class Imu(Base):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

    def frame(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(self.options["header"])
        self.img_draw.text(((w - header_w) / 2, top), self.options["header"], font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"GYRO: x={self.model.data['gyro_x']:.1f} y={self.model.data['gyro_y']:.1f} z={self.model.data['gyro_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"ACC: x={self.model.data['acc_x']:.1f} y={self.model.data['acc_y']:.1f} z={self.model.data['acc_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"ROT: x={self.model.data['rot_x']:.1f} y={self.model.data['rot_y']:.1f}",  font=self.font, fill=255)

        return self.img


class Gps(Base):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

    def frame(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(self.options["header"])
        self.img_draw.text(((w - header_w) / 2, top), self.options["header"], font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"Lat: {self.model.data.latitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Lon: {self.model.data.longitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Alt: {self.model.data.altitude}",  font=self.font, fill=255)

        return self.img
