import logging
import threading
import time
from typing import Any, Dict, List, Union

from luma.core.interface import serial
from luma.oled import device

from PIL import Image, ImageDraw, ImageFont

import gpiozero

from calchas import utils
from calchas.common import base


def _readable_bytes(num: int) -> str:
    """https://stackoverflow.com/a/52379087/53911"""
    step_unit = 1000.0

    for x in ["", "KB", "MB", "GB", "TB"]:
        if num < step_unit:
            return f"{num:.1f} {x}"
        num /= step_unit


class ScreenBase:
    def __init__(self, sensor_name: str, options: Dict[str, Any], model: Any=None):
        self.sensor_name = sensor_name
        self.options = options
        self.model = model
        self.font = ImageFont.load_default()
        self.img = Image.new("1", (self.options["width"], self.options["height"]))
        self.img_draw = ImageDraw.Draw(self.img)

    def wants(self, msg: base.Message) -> bool:
        return self.sensor_name == msg.sensor.name

    def update_model(self, model: Any) -> None:
        self.model = model

    def clear(self) -> Image:
        self.img_draw.rectangle((0, 0, *self.img.size), outline=0, fill=0)
        return self.img

    def frame(self) -> Image:
        return self.clear()

    def mode(self) -> None:
        pass


class SystemInfoScreen(ScreenBase):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

        self._mode_idx = 0
        self._modes = 2

    def frame(self) -> Image:
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize("SYSTEM")
        self.img_draw.text(((w - header_w) / 2, top), "SYSTEM", font=self.font, fill=255)

        if self.model:
            data = self.model.data
            line = 1
            if self._mode_idx == 0:
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
            if self._mode_idx == 1:
                if data:
                    self.img_draw.text((left, top + (line * lineh)), f"DISK: {data['disk_percent']}%",  font=self.font, fill=255)
                    line += 1
                    self.img_draw.text((left, top + (line * lineh)), f"TEMP CPU=:{data['system_cpu_temp']:.2f}°C",  font=self.font, fill=255)
                    line += 1
            # if self._mode_idx == 3:
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

    def mode(self) -> None:
        self._mode_idx = (self._mode_idx + 1) % self._modes


class PiCamScreen(ScreenBase):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

        self._mode_idx = 0
        self._modes = [
            self._camera_stats,
            self._camera_preview,
        ]

    def frame(self) -> Image:
        return self._modes[self._mode_idx]()

    def mode(self) -> None:
        self._mode_idx = (self._mode_idx + 1) % len(self._modes)

    def _camera_stats(self):
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize("PICAM")
        self.img_draw.text(((w - header_w) / 2, top), "PICAM", font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"Frame Type: {self.model.data['frame'].frame_type}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Frame Complete: {self.model.data['frame'].complete}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Frame Size: {_readable_bytes(self.model.data['frame'].frame_size)}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (4 * lineh)), f"Video Size: {_readable_bytes(self.model.data['frame'].video_size)}",  font=self.font, fill=255)

        return self.img

    def _camera_preview(self):
        if not self.model or not self.model.data.get("preview", None):
            self.clear()
            return self.img

        # TODO: define what format the preview image is in
        #image = PIL.Image.open(io.BytesIO(self.model.data['preview']))
        return self.model.data["preview"].resize((128, 64)).convert("1")


class WebcamScreen(ScreenBase):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

    def frame(self) -> Image:
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize("WEBCAM")
        self.img_draw.text(((w - header_w) / 2, top), "WEBCAM", font=self.font, fill=255)

        self.img_draw.text((left, top + (1 * lineh)), f"TODO",  font=self.font, fill=255)
        if self.model:
            pass  # TODO

        return self.img


class ImuScreen(ScreenBase):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

    def frame(self) -> Image:
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize("IMU")
        self.img_draw.text(((w - header_w) / 2, top), "IMU", font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"GYRO: x={self.model.data['gyro_x']:.1f} y={self.model.data['gyro_y']:.1f} z={self.model.data['gyro_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"ACC: x={self.model.data['acc_x']:.1f} y={self.model.data['acc_y']:.1f} z={self.model.data['acc_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"ROT: x={self.model.data['rot_x']:.1f} y={self.model.data['rot_y']:.1f}",  font=self.font, fill=255)

        return self.img


class GpsScreen(ScreenBase):
    def __init__(self, options: Dict[str, Any], model: Any=None):
        super().__init__(options, model)

    def frame(self) -> Image:
        self.clear()
        left, top, lineh = 0, -2, 8

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize("GPS")
        self.img_draw.text(((w - header_w) / 2, top), "GPS", font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"Lat: {self.model.data.latitude or 0.0}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Lon: {self.model.data.longitude or 0.0}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Alt: {self.model.data.altitude or 0.0}",  font=self.font, fill=255)

        return self.img


class Menu:
    def __init__(self, options: Dict[str, Any], flip_fn):
        self.options = options
        self.flip_fn = flip_fn
        self.font = ImageFont.load_default()
        self.screens: List[ScreenBase] = []
        self.screen_idx = 0

        self.btn_prev = None
        self.btn_next = None
        self.btn_mode = None

        if "gpio_pin_prev" in self.options:
            self.btn_prev = gpiozero.Button(self.options["gpio_pin_prev"], bounce_time=.1)
            self.btn_prev.when_pressed = self.prev
        if "gpio_pin_next" in self.options:
            self.btn_next = gpiozero.Button(self.options["gpio_pin_next"], bounce_time=.1)
            self.btn_next.when_pressed = self.next
        if "gpio_pin_mode" in self.options:
            self.btn_mode = gpiozero.Button(self.options["gpio_pin_mode"], bounce_time=.1)
            self.btn_mode.when_pressed = self.mode

    def add_screen(self, screen_name: str):
        screen = self._create_screen(screen_name)
        if screen:
            self.screens.append(screen)

    def prev(self):
        if self.screens:
            self.screen_idx = (self.screen_idx - 1) % len(self.screens)

    def next(self):
        if self.screens:
            self.screen_idx = (self.screen_idx + 1) % len(self.screens)

    def mode(self):
        if self.screens and self.screen_idx < len(self.screens):
            self.screens[self.screen_idx].mode()

    def update(self, msg: base.Message):
        for screen in self.screens or []:
            if screen.wants(msg):
                screen.update_model(msg)
                break

    def display(self):
            self.flip_fn(self.screens[self.screen_idx].frame())

    def _create_screen(self, name: str) -> ScreenBase:
        if name == "systeminfo":
            return SystemInfoScreen(name, self.options)
        elif name == "picam":
            return PiCamScreen(name, self.options)
        elif name == "webcam":
           return WebcamScreen(name, self.options)
        elif name == "imu":
            return ImuScreen(name, self.options)
        elif name == "gps":
            return GpsScreen(name, self.options)
        else:
            logging.error(f"Unknown screen {name}")
            return None


class Monitor(base.Subscriber):
    def __init__(self, options: Dict[str, Any]):
        super().__init__(options)
        self.request_stop = False

        self._render_thread = None

        self.bus = None
        self.disp = None
        self.menu = None

    def on_process_message(self, msg: base.Message):
        self.menu.update(msg)

    def _start_impl(self):
        self.request_stop = False

        self.bus = serial.i2c(port=self.options["port"], address=self.options["address"])
        self.disp = device.ssd1306(self.bus, rotate=self.options.get("rotation", 0))

        self.menu = Menu(self.options, self.disp.display)
        for sensor_name in self.options.get("screens", []):
            self.menu.add_screen(sensor_name)

        self._render_thread = threading.Thread(target=self._render_thread_fn)
        self._render_thread.start()

    def _stop_impl(self):
        self.request_stop = True

        if self._render_thread:
            self._render_thread.join()
            self._render_thread = None

        self.menu = None

        self.disp.cleanup()
        self.disp = None
        self.bus = None

    def _render_thread_fn(self):
        sleep_sec = 1. / self.options.get("framerate", 1.)

        while not self.request_stop:
            self.menu.display()
            time.sleep(sleep_sec - time.time() % sleep_sec)
