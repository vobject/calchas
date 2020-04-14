import datetime
import enum
import logging
import os
import platform
import sys
import threading
import time
from typing import Any, Dict, List, Union

import PIL

from calchas import utils
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
#     def display(self, img: PIL.Image):
#         img_rgba = img.convert("RGBA")
#         img_raw = img_rgba.tobytes()
#         surface = pygame.image.fromstring(img_raw, img_rgba.size, img_rgba.mode)
#         self.screen.blit(surface, (0, 0))
#         pygame.display.flip()


if platform.system() == "Linux":
    import sys
    sys.path.append("/home/pi/calchas2/Adafruit_Python_PureIO")
    sys.path.append("/home/pi/calchas2/Adafruit_Python_GPIO")
    sys.path.append("/home/pi/calchas2/Adafruit_Python_SSD1306")
    import Adafruit_SSD1306
    import gpiozero

    class _Oled:
        def __init__(self, options: Dict[str, Any], menu):
            self.options = options

            self.disp = Adafruit_SSD1306.SSD1306_128_64(rst=None)
            self.disp.begin()
            self.disp.clear()
            self.disp.display()

            self.button = gpiozero.Button(17)
            self.button2 = gpiozero.Button(18)
            self.button.when_pressed = menu.next
            self.button2.when_pressed = menu.mode

        def display(self, img: PIL.Image):
            self.disp.image(img)
            self.disp.display()
else:
    # TODO: protable backend or better fallback
    class _Oled:
        def __init__(self, options: Dict[str, Any], menu):
            pass

        def display(self, img: PIL.Image):
            pass


class Menu:
    def __init__(self, options: Dict[str, Any]=None, backend=None):
        self.options = utils.dict_merge(self.default_options(), options)
        self.font = PIL.ImageFont.load_default()
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
                "width": 128,
                "height": 64,
            },
            "screens": {
                "systeminfo": {
                    "header": "SYSTEM",
                },
                "picamera": {
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

    def previous(self):
        if self.menu_screens:
            self.menu_screen_idx = (self.menu_screen_idx - 1) % len(self.menu_screens)

    def next(self):
        if self.menu_screens:
            self.menu_screen_idx = (self.menu_screen_idx + 1) % len(self.menu_screens)

    def mode(self):
        if self.menu_screens:
            self.menu_screens[self.menu_screen_idx].mode()

    def update(self, entry: Any):
        if self.menu_screens:
            for s in self.menu_screens:
                if s.options["name"] == entry.sensor.name:
                    s.model = entry
                    break

    def display(self):
        if self.backend and self.menu_screens:
            self.backend.display(self.menu_screens[self.menu_screen_idx].frame())

    def exit(self):
        if self.backend and self.menu_screens:
            self.backend.display(self.menu_screens[self.menu_screen_idx].clear())

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
        elif name == "picamera":
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
