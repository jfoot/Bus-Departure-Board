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

def main():
    serial = spi(device=0,port=0, bus_speed_hz=16000000)
    device = ssd1322(serial_interface=serial, framebuffer="diff_to_previous",rotate=2)
 
    z = 0
    Fontmsg = ImageFont.truetype("./lower.ttf",14)
  
    while 1:
        Services = LiveTime.GetData()    
        y = 0
        while y != -1:
            with canvas(device) as draw:    
                drawTime(draw, device)
                if len(Services) == 0:
                    draw.multiline_text(((device.width - draw.textsize("Unable to find laptop.", Fontmsg)[0])/2, 25), "Unable to find laptop.", font=Fontmsg, align="center")
                    y = -1
                else:
                    for x in range(3):
                        if x > len(Services) - 1:
                            break
                        if x == z % 3:
                            y = drawAnimated(Services[x], y, draw, device, Fontmsg, x)
                        else:
                            drawStatic(Services[x], draw, device, Fontmsg, x)
                if y != -1:
                    y = y + 4
        z = z + 1
        if z == 3:
            z = 0
    device.cleanup()
    time.sleep(15)
   

def drawAnimated(service, y, draw, device, Fontmsg, x):  
    if draw.textsize(service.Destination, Fontmsg)[0] - y > 0:
        draw.multiline_text((30 - y,  16 * x),service.Destination , font=Fontmsg, align="left")
    else:
        draw.multiline_text((device.width + draw.textsize(service.Destination, Fontmsg)[0] - y-53,  16 * x),service.Via , font=Fontmsg, align="left")
    draw.rectangle((0,16 * x,30, 16 * x + 16 ), outline="black", fill="black")
    draw.text((0, 16 * x), service.ServiceNumber, font=Fontmsg)
    draw.rectangle((device.width - 54 ,16 * x,device.width,16 + 16 * x), outline="black", fill="black")
    draw.multiline_text(((device.width - draw.textsize(service.DisplayTime, Fontmsg)[0]- 3),  16 * x),service.DisplayTime, font=Fontmsg, align="right")  
     
    
    if draw.textsize(service.Destination, Fontmsg)[0] + draw.textsize(service.Via, Fontmsg)[0] + device.width - y -20 < 0:
        return -1
    return y

def drawStatic(service, draw, device, Fontmsg, x):
    draw.multiline_text((30, 16 * x),service.Destination, font=Fontmsg, align="left")
    draw.text((0, 16 * x),service.ServiceNumber, font=Fontmsg)
    draw.multiline_text(((device.width - draw.textsize(service.DisplayTime, Fontmsg)[0]- 3),  16 * x), service.DisplayTime, font=Fontmsg, align="right")

def drawTime(draw, device):
    FontTime = ImageFont.truetype("./time.otf",16)
    msgTime = str(datetime.now().strftime('%H:%M'))
    draw.multiline_text(((device.width - draw.textsize(msgTime, FontTime)[0])/2, device.height-16), msgTime, font=FontTime, align="center")

if __name__ == '__main__':
    main()
