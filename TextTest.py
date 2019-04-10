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


class LiveTime(object):
    def __init__(self, Data):
        self.ServiceNumber = str(Data.LineRef)
        self.Destination = str(Data.DestinationName)
        self.SchArrival = str(Data.MonitoredCall.AimedArrivalTime).split("+")[0]
        self.ExptArrival = str(getattr( Data.MonitoredCall, "ExpectedArrivalTime", "")).split("+")[0]
        self.Via = str(getattr(Data, "Via", "Unknown"))
        self.DisplayTime = self.GetDisplayTime()
        self.ID =  str(Data.FramedVehicleJourneyRef.DatedVehicleJourneyRef)
  
    def GetDisplayTime(self):
        if self.ExptArrival == "":
            return  str(datetime.strptime(self.SchArrival, '%Y-%m-%dT%H:%M:%S').time())[:-3]
        else:
            Diff =  (datetime.strptime(self.ExptArrival, '%Y-%m-%dT%H:%M:%S') - datetime.now()).total_seconds() / 60
            if Diff <= 2:
                return 'Due'
            if Diff >=15 :
                return str(datetime.strptime(self.SchArrival, '%Y-%m-%dT%H:%M:%S').time())[:-3]
            return  '%d min' % Diff

    @staticmethod
    def GetData():
        services = []
        try:
            raw = urllib2.urlopen("https://rtl2.ods-live.co.uk/api/siri/sm?key=%s&location=039028160001" % sys.argv[1]).read()
            rawServices = objectify.fromstring(raw)
        
            for root in rawServices.ServiceDelivery.StopMonitoringDelivery.MonitoredStopVisit:
                service = root.MonitoredVehicleJourney
                exsits = False
                for current in services:
                    if current.ID == service.FramedVehicleJourneyRef.DatedVehicleJourneyRef:
                        exsits = True
                        break

                if exsits == False:
                    services.append(LiveTime(service))
            return services
        except Exception as e:
            print(str(e))
            return []



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

class Record():
    WAIT_SCROLL = 1
    SCROLLING = 2
    WAIT_REWIND = 3
    WAIT_SYNC = 4

    def __init__(self, image_composition, service, scroll_delay, synchroniser, device):
        font = ImageFont.truetype("./lower.ttf",14)
        displayTimeTemp = TextImage(device, service.DisplayTime, font)

        self.image_composition = image_composition
        self.speed = 1
        self.image_x_pos = 0
        
        self.Destination =  ComposableImage(TextImage(device, service.Destination, font).image, position=(30, 0))
        self.ServiceNumber =  ComposableImage(TextImage(device, service.ServiceNumber, font).image, position=(0, 0))
        self.DisplayTime =  ComposableImage(displayTimeTemp.image, position=((device.width - displayTimeTemp.width- 3), 16))

        self.image_composition.add_image(ServiceNumber)
        self.image_composition.add_image(DisplayTime)
        self.image_composition.add_image(Destination)

        self.max_pos = Destination.width + image_composition().width
        self.delay = scroll_delay
        self.ticks = 0
        self.state = self.WAIT_SCROLL
        self.synchroniser = synchroniser
        self.render()
        self.synchroniser.busy(self)
        self.cycles = 0
        self.must_scroll = self.max_pos > 0

    def __del__(self):
        self.image_composition.remove_image(self.Destination)

    def tick(self):

        # Repeats the following sequence:
        #  wait - scroll - wait - rewind -> sync with other scrollers -> wait
        if self.state == self.WAIT_SCROLL:
            if not self.is_waiting():
                self.cycles += 1
                self.state = self.SCROLLING
                self.synchroniser.busy(self)

        elif self.state == self.WAIT_REWIND:
            if not self.is_waiting():
                self.synchroniser.ready(self)
                self.state = self.WAIT_SYNC

        elif self.state == self.WAIT_SYNC:
            if self.synchroniser.is_synchronised():
                if self.must_scroll:
                    self.image_x_pos = 0
                    self.render()
                self.state = self.WAIT_SCROLL

        elif self.state == self.SCROLLING:
            if self.image_x_pos < self.max_pos:
                if self.must_scroll:
                    self.render()
                    self.image_x_pos += self.speed
            else:
                self.state = self.WAIT_REWIND

    def render(self):
        self.Destination.offset = (self.image_x_pos, 0)

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
            Services = LiveTime.GetData()    
            Record(image_composition, Services[0], 100, synchroniser, device)

            cycles = 0

            while cycles < 3:
                Record.tick()
                time.sleep(0.025)
                cycles = Record.get_cycles()

                with canvas(device, background=image_composition()) as draw:
                    image_composition.refresh()
                    draw.rectangle(device.bounding_box, outline="white")

            del Record

except KeyboardInterrupt:
    pass