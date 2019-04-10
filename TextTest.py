import urllib2
import time
import sys
from luma.core.render import canvas
from luma.core.interface.serial import spi
from luma.core.virtual import viewport, snapshot
from luma.oled.device import ssd1322
from PIL import ImageFont, Image, ImageDraw
from lxml import objectify
from datetime import datetime, date
from luma.core.image_composition import ImageComposition, ComposableImage


class TextImage():
    def __init__(self, device, text, font):
        with canvas(device) as draw:
            w, h = draw.textsize(text, font)
        self.image = Image.new(device.mode, (w, h))
        draw = ImageDraw.Draw(self.image)
        draw.text((0, 0), text, font=font, fill="white")
        del draw
        self.width = w
        self.height = h

class Synchroniser():
    def __init__(self):
        self.synchronised = {}

    def busy(self, task):
        self.synchronised[id(task)] = False

    def ready(self, task):
        self.synchronised[id(task)] = True

    def is_synchronised(self):
        for task in self.synchronised.items():
            if task[1] is False:
                return False
        return True

class Scroller():
    WAIT_SCROLL = 1
    SCROLLING = 2
    #WAIT_REWIND = 3
    #WAIT_SYNC = 4

    def __init__(self, image_composition, rendered_image, scroll_delay, synchroniser):
        self.image_composition = image_composition
        self.speed = 1
        self.image_x_pos = 0
        self.rendered_image = rendered_image
        self.image_composition.add_image(rendered_image)
        self.max_pos = rendered_image.width - image_composition().width #Changed this to a + from a -
        self.delay = scroll_delay
        self.ticks = 0
        self.state = self.WAIT_SCROLL
        self.synchroniser = synchroniser
        self.render()
        self.synchroniser.busy(self)
        self.cycles = 0
        self.must_scroll = self.max_pos > 0

    def __del__(self):
        self.image_composition.remove_image(self.rendered_image)

    def tick(self):

        # Repeats the following sequence:
        #  wait - scroll - wait - rewind -> sync with other scrollers -> wait
        if self.state == self.WAIT_SCROLL:
            if not self.is_waiting():
                self.cycles += 1
                self.state = self.SCROLLING
                self.synchroniser.busy(self)

        elif self.state == self.SCROLLING:
            if self.image_x_pos < self.max_pos:
                if self.must_scroll:
                    self.render()
                    self.image_x_pos += self.speed
            else:
                self.image_x_pos = 0
                self.render()

    def render(self):
        self.rendered_image.offset = (self.image_x_pos, 0)

    def is_waiting(self):
        self.ticks += 1
        if self.ticks > self.delay:
            self.ticks = 0
            return False
        return True

    def get_cycles(self):
        return self.cycles


serial = spi(device=0,port=0, bus_speed_hz=16000000)
device = ssd1322(serial_interface=serial, framebuffer="diff_to_previous",rotate=2)
image_composition = ImageComposition(device)
font = ImageFont.truetype("./lower.ttf",14)



locations = [
    "Caversham Heights",
    "Emmer Green",
    "Caversham Park",
    "Reading Station"
]
try:
    while True:
        for location in locations:
            synchroniser = Synchroniser()
            ci_loc =  ComposableImage(TextImage(device, location, font).image, position=(0, 16))
            Loc = Scroller(image_composition, ci_loc, 100, synchroniser)

            cycles = 0

            while cycles < 3:
                Loc.tick()
                time.sleep(0.025)
                cycles = Loc.get_cycles()

                with canvas(device, background=image_composition()) as draw:
                    image_composition.refresh()
                    draw.rectangle(device.bounding_box, outline="white")

            del Loc

except KeyboardInterrupt:
    pass