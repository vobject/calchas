import datetime
import enum
import logging
import os
import platform
import sys
import threading
import time
from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw, ImageFont

from calchas import utils
from calchas.sensors import base as sensorbase
from calchas.ui import screen


# if platform.system() == "Windows":
    # import pygame

# class _Pygame:
#     def __init__(self, options: Dict[str, Any]):
#         self.options = options
#
#         os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
#
#         pygame.init()
#         self.screen = pygame.display.set_mode([self.options["width"], self.options["height"]])
#
#     def input(self, menu):
#         for event in pygame.event.get():
#             if event.type == pygame.KEYDOWN:
#                 if event.key == pygame.K_LEFT:
#                     menu.previous()
#                 if event.key == pygame.K_RIGHT:
#                     menu.next()
#                 if event.key == pygame.K_SPACE:
#                     menu.mode()
#
#     def display(self, img: Image):
#         img_rgba = img.convert("RGBA")
#         img_raw = img_rgba.tobytes()
#         surface = pygame.image.fromstring(img_raw, img_rgba.size, img_rgba.mode)
#         self.screen.blit(surface, (0, 0))
#         pygame.display.flip()


if platform.system() == "Linux":
    import gpiozero
    from luma.core.interface import serial
    from luma.oled import device

    class _Oled:
        def __init__(self, options: Dict[str, Any], menu):
            self.options = options

            self.bus = serial.i2c(port=self.options["port"], address=self.options["address"])
            self.disp = device.ssd1306(self.bus, rotate=self.options["rotation"])

            self.button = gpiozero.Button(17, bounce_time=.1)
            self.button2 = gpiozero.Button(18, bounce_time=.1)
            self.button3 = gpiozero.Button(27, bounce_time=.1)
            self.button.when_pressed = menu.prev
            self.button2.when_pressed = menu.mode
            self.button3.when_pressed = menu.next

        def display(self, img: Image):
            self.disp.display(img)
else:
    # TODO: portable backend or better fallback
    class _Oled:
        def __init__(self, options: Dict[str, Any], menu):
            pass

        def display(self, img: Image):
            pass


class Menu:
    def __init__(self, options: Dict[str, Any]=None, backend=None):
        self.options = utils.dict_merge(self.default_options(), options)
        self.font = ImageFont.load_default()
        self.backend = backend or self._select_backend()
        self.menu_screen_idx = 0
        self.menu_screens: List[screen.Base] = []

    def default_options(self):
        return {
            "backend": {
                # "type": "pygame",
                "type": "SDD1306",
                "active": False,
                "dry-run": False,
                "port": 1,
                "address": 0x3c,
                "rotation": 0,  # 0==0°, 1==90°, 2==180°, 3==270° clockwise
                "width": 128,
                "height": 64,
            },
            "screens": {
                "systeminfo": {
                    "header": "SYSTEM",
                },
                "picam": {
                    "header": "PICAMERA",
                },
                "webcam": {
                    "header": "WEBCAM",
                },
                "imu": {
                    "header": "IMU",
                },
                "gps": {
                    "header": "GPS",
                },
            }
        }

    def add_screen(self, screen: Union[str, screen.Base], options: Dict[str, Any]=None):
        if isinstance(screen, str):
            screen = self._create_screen(screen, options)
        self.menu_screens.append(screen)

    def prev(self):
        if self.menu_screens:
            self.menu_screen_idx = (self.menu_screen_idx - 1) % len(self.menu_screens)

    def next(self):
        if self.menu_screens:
            self.menu_screen_idx = (self.menu_screen_idx + 1) % len(self.menu_screens)

    def mode(self):
        if self.menu_screens:
            self.menu_screens[self.menu_screen_idx].mode()

    def update(self, msg: sensorbase.Message):
        if self.menu_screens:
            for s in self.menu_screens:
                if s.options["name"] == msg.sensor.name:
                    s.model = msg
                    break

    def display(self):
        if self.backend and self.menu_screens:
            self.backend.display(self.menu_screens[self.menu_screen_idx].frame())

    def exit(self):
        if self.backend and self.menu_screens:
            self.backend.display(self.menu_screens[self.menu_screen_idx].clear())
            self.backend.disp.cleanup()  # FIXME

    def _select_backend(self):
        backend_type = self.options["backend"]["type"]
        if backend_type == "SDD1306":
            return _Oled(self.options["backend"], self)
        # elif backend_type == "pygame":
        #     return _Pygame(self.options["backend"])
        elif backend_type == "httpsrv":
            raise NotImplementedError

    def _create_screen(self, name: str, options: Dict[str, Any]=None) -> screen.Base:
        screen_options = utils.dict_merge(self.options["screens"].get(name, None).copy(), { "name": name, "width": self.options["backend"]["width"], "height": self.options["backend"]["height"] })
        screen_options = utils.dict_merge(screen_options, options)
        if name == "systeminfo":
            return screen.SystemInfo(screen_options)
        elif name == "picam":
            return screen.PiCamera(screen_options)
        elif name == "webcam":
           return screen.Webcam(screen_options)
        elif name == "imu":
            return screen.Imu(screen_options)
        elif name == "gps":
            return screen.Gps(screen_options)

    #def _input_thread_fn(self):
    #    while not self.request_stop:
    #        if self.backend and self.menu_screens:
    #            self.backend.input(self)
    #        time.sleep(.1)
