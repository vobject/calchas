import datetime
import logging
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont


class Base:
    def __init__(self, options: Dict[str, Any], model: Any=None):
        self.options = options
        self.model = model
        self.font = self.options.get("font", ImageFont.load_default())
        self.img = Image.new("1", (self.options["width"], self.options["height"]))
        self.img_draw = ImageDraw.Draw(self.img)

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
        self._modes = 3

    def frame(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(self.options["header"])
        self.img_draw.text(((w - header_w) / 2, top), self.options["header"], font=self.font, fill=255)

        if self.model:
            line = 1
            if self._mode == 0:
                x = self.model.state.get("process", None)
                if x:
                    self.img_draw.text((left, top + (line * lineh)), f"CPU: {x['cpu_percent']}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"RSS: {x['mem_rss']}",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"VMS: {x['mem_vms']}",  font=self.font, fill=255)
                    line += 1
            if self._mode == 1:
                x = self.model.state.get("filesystem", None)
                if x:
                    for k, v in x.items():
                        self.img_draw.text((left, top + (line * lineh)), f"DISK: {k}={v['percent']}%",  font=self.font, fill=255)
                        line += 1
            if self._mode == 2:
                x = self.model.state.get("temperature", None)
                if x:
                    self.img_draw.text((left, top + (line * lineh)), f"TEMP CPU=:{x['cpu']:.2f}°C",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"TEMP GPU=:{x['gpu']:.2f}°C",  font=self.font, fill=255)
                    line += 1

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
            self.img_draw.text((left, top + (1 * lineh)), f"Frame Type: {self.model.state['frame'].frame_type}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Frame Complete: {self.model.state['frame'].complete}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Frame Size: {self.model.state['frame'].frame_size}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (4 * lineh)), f"Video Size: {self.model.state['frame'].video_size}",  font=self.font, fill=255)

        return self.img

    def _camera_preview(self):
        if not self.model or not self.model.state["preview"]:
            self.clear()
            return self.img

        # TODO: define what format the preview image is in
        #image = Image.open(io.BytesIO(self.model.state['preview']))
        return self.model.state["preview"].resize((128, 64)).convert("1")


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
            self.img_draw.text((left, top + (1 * lineh)), f"GYRO: x={self.model.state['gyro_x']:.1f} y={self.model.state['gyro_y']:.1f} z={self.model.state['gyro_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"ACC: x={self.model.state['acc_x']:.1f} y={self.model.state['acc_y']:.1f} z={self.model.state['acc_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"ROT: x={self.model.state['rot_x']:.1f} y={self.model.state['rot_y']:.1f}",  font=self.font, fill=255)

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
            self.img_draw.text((left, top + (1 * lineh)), f"Lat: {self.model.state.latitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Lon: {self.model.state.longitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Alt: {self.model.state.altitude}",  font=self.font, fill=255)

        return self.img
