# TODO:
# ui/ subfolder with sensor-ui implementations
# and menu class
# and selectable menu implementation (sd1306 or pygame)

import datetime
import logging
import time

from PIL import Image, ImageDraw, ImageFont


class MenuScreenBase:
    def __init__(self, w, h, font, model=None):
        self.font = font
        self.model = model
        self.img = Image.new("1", (w, h))
        self.img_draw = ImageDraw.Draw(self.img)

    def _clear_image(self):
        self.img_draw.rectangle((0,0,*self.img.size), outline=0, fill=0)

    def frame(self):
        return self._clear_image()

    def mode(self):
        pass


class SysInfoScreen(MenuScreenBase):
    def __init__(self, w, h, font, model):
        super().__init__(w, h, font, model)

    def frame(self):
        self._clear_image()
        left, top, lineh = 0, -2, 8
        header = "SYSTEM"

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(header)
        self.img_draw.text(((w - header_w) / 2, top), header, font=self.font, fill=255)

        if self.model:
            line = 1
            if "process" in self.model.state and self.model.state["process"]:
                x = self.model.state["process"]
                self.img_draw.text((left, top + (line * lineh)), f"CPU: {x['cpu_percent']}%",  font=self.font, fill=255)
                line += 1
                self.img_draw.text((left, top + (line * lineh)), f"RSS: {x['mem_rss']}",  font=self.font, fill=255)
                line += 1
                self.img_draw.text((left, top + (line * lineh)), f"VMS: {x['mem_vms']}",  font=self.font, fill=255)
                line += 1
            if "filesystem" in self.model.state and self.model.state["filesystem"]:
                for k, v in self.model.state["filesystem"].items():
                    self.img_draw.text((left, top + (line * lineh)), f"DISK: {k}={v['percent']}%",  font=self.font, fill=255)
                    line += 1
            if "temperature" in self.model.state and self.model.state["temperature"]:
                x = self.model.state["temperature"]
                self.img_draw.text((left, top + (line * lineh)), f"TEMP CPU=:{x['cpu']:.2f}°C",  font=self.font, fill=255)
                line += 1
                self.img_draw.text((left, top + (line * lineh)), f"TEMP GPU=:{x['gpu']:.2f}°C",  font=self.font, fill=255)
                line += 1

        return self.img


class PiCameraScreen(MenuScreenBase):
    def __init__(self, w, h, font, model):
        super().__init__(w, h, model)
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
        self._clear_image()
        left, top, lineh = 0, -2, 8
        header = "PICAMERA"

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(header)
        self.img_draw.text(((w - header_w) / 2, top), header, font=self.font, fill=255)

        if not self.model:
            return self.img

        self.img_draw.text((left, top + (1 * lineh)), f"Frame Type: {self.model.state['frame'].frame_type}",  font=self.font, fill=255)
        self.img_draw.text((left, top + (2 * lineh)), f"Frame Complete: {self.model.state['frame'].complete}",  font=self.font, fill=255)
        self.img_draw.text((left, top + (3 * lineh)), f"Frame Size: {self.model.state['frame'].frame_size}",  font=self.font, fill=255)
        self.img_draw.text((left, top + (4 * lineh)), f"Video Size: {self.model.state['frame'].video_size}",  font=self.font, fill=255)

        return self.img

    def _camera_preview(self):
        if not self.model or not self.model.state["preview"]:
            self._clear_image()
            return self.img

        # TODO: define what format the preview image is in
        #image = Image.open(io.BytesIO(self.model.state['preview']))
        return self.model.state["preview"].resize((128, 64)).convert("1")


class ImuScreen(MenuScreenBase):
    def __init__(self, w, h, font, model):
        super().__init__(w, h, font, model)

    def frame(self):
        self._clear_image()
        left, top, lineh = 0, -2, 8
        header = "IMU"

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(header)
        self.img_draw.text(((w - header_w) / 2, top), header, font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"GYRO: x={self.model.state['gyro_x']:.1f} y={self.model.state['gyro_y']:.1f} z={self.model.state['gyro_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"ACC: x={self.model.state['acc_x']:.1f} y={self.model.state['acc_y']:.1f} z={self.model.state['acc_z']:.1f}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"ROT: x={self.model.state['rot_x']:.1f} y={self.model.state['rot_y']:.1f}",  font=self.font, fill=255)

        return self.img


class GpsScreen(MenuScreenBase):
    def __init__(self, w, h, font, model):
        super().__init__(w, h, font, model)

    def frame(self):
        self._clear_image()
        left, top, lineh = 0, -2, 8
        header = "GPS"

        w, _ = self.img.size
        header_w, _ = self.img_draw.textsize(header)
        self.img_draw.text(((w - header_w) / 2, top), header, font=self.font, fill=255)

        if self.model:
            self.img_draw.text((left, top + (1 * lineh)), f"Lat: {self.model.state.latitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (2 * lineh)), f"Lon: {self.model.state.longitude}",  font=self.font, fill=255)
            self.img_draw.text((left, top + (3 * lineh)), f"Alt: {self.model.state.altitude}",  font=self.font, fill=255)

        return self.img


class Menu:
    def __init__(self, w, h, display_flip):
        self.font = ImageFont.load_default()
        self.menu_screen_idx = 0
        self.menu_screens = []
        self.display_flip = display_flip

    def add_screen(self, screen: MenuScreenBase):
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

    def display(self):
        if self.menu_screens:
            self.display_flip(self.menu_screens[self.menu_screen_idx].frame())


class FakeSystemInfoModel:
    @property
    def state(self):
        import os
        import psutil
        process = psutil.Process(os.getpid())
        meminfo = process.memory_info()
        return {
            "timestamp": time.time(),
            "filesystem": {
                part.mountpoint: {
                    "total": psutil.disk_usage(part.mountpoint)[0],
                    "used": psutil.disk_usage(part.mountpoint)[1],
                    "free": psutil.disk_usage(part.mountpoint)[2],
                    "percent": psutil.disk_usage(part.mountpoint)[3],
                } for part in psutil.disk_partitions()
            },
            "process": {
                "cpu_percent": process.cpu_percent(interval=.1),
                "mem_rss": meminfo.rss,
                "mem_vms": meminfo.vms,
            },
            # "temperature": {
            #     "cpu": 0,  #psutil.sensors_temperatures()  # Linux only
            #     "gpu": 0,
            # },
        }


def run_pygame_demo():
    import os
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
    import pygame

    def pygame_display(screen, img):
        img_rgba = img.convert("RGBA")
        img_raw = img_rgba.tobytes()
        surface = pygame.image.fromstring(img_raw, img_rgba.size, img_rgba.mode)
        screen.blit(surface, (0, 0))
        pygame.display.flip()


    w, h = 128, 64

    pygame.init()
    clock = pygame.time.Clock()
    screen = pygame.display.set_mode([w, h])

    menu = Menu(w, h, lambda img: pygame_display(screen, img))
    menu.add_screen(SysInfoScreen(w, h, menu.font, FakeSystemInfoModel()))
    menu.add_screen(PiCameraScreen(w, h, menu.font, None))
    menu.add_screen(ImuScreen(w, h, menu.font, None))
    menu.add_screen(GpsScreen(w, h, menu.font, None))

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                if event.key == pygame.K_LEFT:
                    menu.previous()
                if event.key == pygame.K_RIGHT:
                    menu.next()
                if event.key == pygame.K_SPACE:
                    menu.mode()

        menu.display()
        clock.tick(10)

    pygame.quit()


def run_sdd1306_demo():
    import sys
    sys.path.append("/home/pi/calchas2/Adafruit_Python_PureIO")
    sys.path.append("/home/pi/calchas2/Adafruit_Python_GPIO")
    sys.path.append("/home/pi/calchas2/Adafruit_Python_SSD1306")

    import Adafruit_SSD1306

    disp = Adafruit_SSD1306.SSD1306_128_64(rst=None)
    disp.begin()
    disp.clear()
    disp.display()

    def oled_display(disp, img):
        disp.image(img)
        disp.display()

    w, h = disp.width, disp.height

    menu = Menu(w, h, lambda img: oled_display(disp, img))
    menu.add_screen(SysInfoScreen(w, h, menu.font, FakeSystemInfoModel()))
    menu.add_screen(PiCameraScreen(w, h, menu.font, None))
    menu.add_screen(ImuScreen(w, h, menu.font, None))
    menu.add_screen(GpsScreen(w, h, menu.font, None))

    while True:
        menu.display()
        time.sleep(1.)


def main():
    import argparse
    run_pygame_demo()
    #run_sdd1306_demo()


if __name__ == "__main__":
    main()
