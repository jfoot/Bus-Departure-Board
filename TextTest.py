import urllib2
import json
import time
import sys
import math
from PIL import ImageFont, Image, ImageDraw
from luma.core.render import canvas
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from lxml import objectify
from datetime import datetime, date
from luma.core.image_composition import ImageComposition, ComposableImage

###
# Below contains the class which gets API data from the Reading Buses API. You should pass the API key in as a paramater on startup.
###
#Used to create a blank object, needed in start-up or when there are less than 3 services currently schedualed. 
class LiveTimeStud():
	def __init__(self):
		self.ServiceNumber = " "
		self.Destination = " "
		self.DisplayTime = " "
		self.SchArrival = " "
		self.ExptArrival = " "
		self.Via = " "
		self.ID =  " "
		self.Operator = " "
	
#Used to get live data from the Reading Buses API.
class LiveTime(object):
	def __init__(self, Data, Type):
		self.Type = Type
		if Type == "RB":
			self.ID =  str(Data.FramedVehicleJourneyRef.DatedVehicleJourneyRef)
			self.Operator = "Reading Buses"
			self.ServiceNumber = str(Data.LineRef)
			self.Destination = str(Data.DestinationName)
			self.SchArrival = str(Data.MonitoredCall.AimedArrivalTime).split("+")[0]
			self.ExptArrival = str(getattr( Data.MonitoredCall, "ExpectedArrivalTime", "")).split("+")[0]
			self.Via = str(getattr(Data, "Via", "Unknown"))
			self.DisplayTime = self.GetDisplayTime()
		if Type == "OTH":
			self.ID =  str(Data['id'])
			self.Operator = str(Data['operator_name'])
			self.ServiceNumber = str(Data['line'])
			self.Destination = str(Data['direction'])
			self.SchArrival = str(Data['aimed_departure_time']) 	#This seems like it's the wrong way around, possiable API bug
			self.ExptArrival = str(Data['best_departure_estimate'])
			self.Via = self.GetComplexVia()
			self.DisplayTime = self.GetDisplayTime()
			
  
	def GetComplexVia(self):
		Via = "This is a " + self.Operator + " Service"
		#Need to fix this so it removes repeated location suffixs.
		#Need to make this optional such that it doesn't slow Pi down if not wantted.
		#Need to make this more efficent, if it has already seen this bus before do NOT get the data again.

		try:
			tempLocs = json.loads(urllib2.urlopen(self.ID).read())
			Via += ", via: "
			for loc in tempLocs['stops']:
				if loc['locality'] not in Via:
					Via += loc['locality'] + ", "

			#NEED to make this optional
			self.Destination = tempLocs['stops'][-1]['stop_name']
			return Via[:-2] + "."
		except Exception as e:
			print(str(e))
		return Via + "."
	


				


	def GetDisplayTime(self):
		if self.Type == "RB":
			if self.ExptArrival == "":
				return " " + str(datetime.strptime(self.SchArrival, '%Y-%m-%dT%H:%M:%S').time())[:-3]
			else:
				Diff =  (datetime.strptime(self.ExptArrival, '%Y-%m-%dT%H:%M:%S') - datetime.now()).total_seconds() / 60
				if Diff <= 2:
					return ' Due'
				if Diff >=15 :
					return ' ' + str(datetime.strptime(self.ExptArrival, '%Y-%m-%dT%H:%M:%S').time())[:-3] #-3 to remove seconds
				return  ' %d min' % Diff
		
		if self.Type == "OTH":
			Arrival = datetime.strptime(str(datetime.now().date()) + " "  + self.ExptArrival, '%Y-%m-%d %H:%M')
			
			Diff =  (Arrival - datetime.now()).total_seconds() / 60
			if Diff <= 2:
				return ' Due'
			if Diff >=15 :
				return ' ' + str(Arrival.time())[:-3] #-3 to remove seconds
			return  ' %d min' % Diff

	@staticmethod
	def GetData():
		services = []
		
		if sys.argv[2] == "RB":	
			try:
				raw = urllib2.urlopen("https://rtl2.ods-live.co.uk/api/siri/sm?key=%s&location=039025980002" % sys.argv[1]).read()
				rawServices = objectify.fromstring(raw)
			
				for root in rawServices.ServiceDelivery.StopMonitoringDelivery.MonitoredStopVisit:
					service = root.MonitoredVehicleJourney
					exsits = False
					for current in services:
						if current.ID == service.FramedVehicleJourneyRef.DatedVehicleJourneyRef:
							exsits = True
							break

					if exsits == False:
						services.append(LiveTime(service, "RB"))
				return services
			except Exception as e:
				print(str(e))
				return []

		#Need to make proper tagging system
		if sys.argv[2] == "OTH":
			try:
				tempServices = json.loads(urllib2.urlopen("https://transportapi.com/v3/uk/bus/stop/3390UN36/live.json?app_id="+ sys.argv[3]+"&app_key=" + sys.argv[1] + "&group=no&limit=9&nextbuses=yes").read())
				for service in tempServices['departures']['all']:
					services.append(LiveTime(service, "OTH"))
				return services
			except Exception as e:
				print(str(e))
				return []


###
# Below contains everything for the drawing and animating of the board.
###

#Used to create the time and service number on the board
class TextImage():
	def __init__(self, device, text, font):
		self.image = Image.new(device.mode, (device.width, 16))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), text, font=font, fill="white")
	
		self.width = 5 + draw.textsize(text, font)[0]
		self.height = 5 + draw.textsize(text, font)[1]
		del draw

#Used to create the destination and via board.
class TextImageComplex():
	def __init__(self, device, destination, via, font, startOffset):
		self.image = Image.new(device.mode, (device.width*10, 16))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), destination, font=font, fill="white")
		draw.text((device.width - startOffset, 0), via, font=font, fill="white")
			
		self.width = device.width + draw.textsize(via, font)[0]  - startOffset
		self.height = 16
		del draw

#Used for the opening animation, creates a static two lines of the new and previous service.
class StaticTextImage():
	def __init__(self, device, service, previous_service, font):			
		self.image = Image.new(device.mode, (device.width, 32))
		draw = ImageDraw.Draw(self.image)
		displayTimeTempPrevious = TextImage(device, previous_service.DisplayTime, font)
		displayTimeTemp = TextImage(device, service.DisplayTime, font)

		draw.text((0, 16), service.ServiceNumber, font=font, fill="white")
		draw.text((device.width - displayTimeTemp.width, 16), service.DisplayTime, font=font, fill="white")
		draw.text((30, 16), service.Destination, font=font, fill="white")	

		draw.text((30, 0), previous_service.Destination, font=font, fill="white")	
		draw.text((0, 0), previous_service.ServiceNumber, font=font, fill="white")
		draw.text((device.width - displayTimeTempPrevious.width, 0), previous_service.DisplayTime, font=font, fill="white")
	
		self.width = device.width 
		self.height = 32
		del draw

#Used to draw a black cover over hidden stuff.
class RectangleCover():
	def __init__(self, device):		
		w = device.width
		h = 16
			
		self.image = Image.new(device.mode, (w, h))
		draw = ImageDraw.Draw(self.image)
		draw.rectangle((0, 0, device.width,16), outline="black", fill="black")

		del draw
		self.width = w 
		self.height = h

class NoService():
	def __init__(self, device, font):		
		w = device.width
		h = 16
		msg = "No Scheduled Services Found"
		self.image = Image.new(device.mode, (w, h))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), msg, font=font, fill="white")

	
		self.width = draw.textsize(msg, font=font)[0]
		self.height = draw.textsize(msg, font=font)[1]
		del draw
		
#Syncroniser
#Used to ensure that only 1 animation is playing at any given time, apart from at the start; where all three can animate in.
class Synchroniser():
	def __init__(self):
		self.synchronised = {}

	def busy(self, task):
		self.synchronised[id(task)] = False

	def ready(self, task):
		self.synchronised[id(task)] = True

	def is_synchronised(self):
		for task in self.synchronised.items():
			if task[1] == False:
				return False
		return True

#Board Line
#Defines what one line of the display will show, i.e. what serivce that row is an what animation it should currently be running 
class ScrollTime():
	WAIT_OPENING = 0
	OPENING_SCROLL = 1
	OPENING_END  = 2
	WAIT_SCROLL = 3
	SCROLLING_SYNC = 6
	SCROLLING_WAIT = 7
	SCROLLING = 4
	WAIT_SYNC = 5
	
	
	def __init__(self, image_composition, service, previous_service, scroll_delay, synchroniser, device, position, controller):
		self.font = ImageFont.truetype("./lower.ttf",14)

		self.speed = 3
		self.position = position
		self.Controller = controller
		
		self.image_composition = image_composition
		self.rectangle = ComposableImage(RectangleCover(device).image, position=(0,16 * position + 16))
		self.CurrentService = service
		
		self.generateCard(service)
		
		self.IStaticOld =  ComposableImage(StaticTextImage(device,service, previous_service, self.font).image, position=(0, (16 * position)))
		
		self.image_composition.add_image(self.IStaticOld)
		self.image_composition.add_image(self.rectangle)
		
		self.max_pos = self.IDestination.width
		self.image_y_posA = 0
		self.image_x_pos = 0

		self.partner = None
			
		self.delay = scroll_delay
		self.ticks = 0
		self.state = self.OPENING_SCROLL
		self.synchroniser = synchroniser
		self.render()
		self.synchroniser.ready(self)

	def generateCard(self,service):
		displayTimeTemp = TextImage(device, service.DisplayTime, self.font)
		IDestinationTemp  = TextImageComplex(device, service.Destination,service.Via, self.font, displayTimeTemp.width)

		self.IDestination =  ComposableImage(IDestinationTemp.image.crop((0,0,IDestinationTemp.width + 10,16)), position=(30, 16 * self.position))
		self.IServiceNumber =  ComposableImage(TextImage(device, service.ServiceNumber, self.font).image.crop((0,0,30,16)), position=(0, 16 * self.position))
		self.IDisplayTime =  ComposableImage(displayTimeTemp.image, position=(device.width - displayTimeTemp.width, 16 * self.position))

	def changeCard(self, newService, device):
		self.state = self.WAIT_OPENING
		self.synchroniser.busy(self)

		self.IStaticOld =  ComposableImage(StaticTextImage(device,newService, self.CurrentService, self.font).image, position=(0, (16 * self.position)))
	
		self.image_composition.add_image(self.IStaticOld)
		self.image_composition.add_image(self.rectangle)
		self.image_composition.remove_image(self.IDestination)
		self.image_composition.remove_image(self.IServiceNumber)
		self.image_composition.remove_image(self.IDisplayTime)
		if self.partner != None:
			self.partner.refresh()
			
		self.image_composition.refresh()
		del self.IDestination
		del self.IServiceNumber
		del self.IDisplayTime

		self.generateCard(newService)
		self.CurrentService = newService
		self.max_pos = self.IDestination.width
		self.state = self.WAIT_OPENING
		


	def __del__(self):
		try:
			self.image_composition.remove_image(self.IStaticOld)
			self.image_composition.remove_image(self.rectangle)
		except:
   			pass
		try:
			self.image_composition.remove_image(self.IDestination)
			self.image_composition.remove_image(self.IServiceNumber)
			self.image_composition.remove_image(self.IDisplayTime)
		except:
			pass
		
		
	

	def tick(self):
		if self.state == self.WAIT_OPENING:
			if not self.is_waiting():
				self.state = self.OPENING_SCROLL
		elif self.state == self.OPENING_SCROLL:
			if self.image_y_posA < 16:              
				self.render()
				self.image_y_posA += self.speed
			else:
				self.state = self.OPENING_END

		elif self.state == self.OPENING_END:
			self.image_x_pos = 0
			self.image_y_posA = 0
			self.image_composition.remove_image(self.IStaticOld)
			self.image_composition.remove_image(self.rectangle)
			del self.IStaticOld

			self.image_composition.add_image(self.IDestination)
			self.image_composition.add_image(self.IServiceNumber)
			self.image_composition.add_image(self.IDisplayTime)		
			self.render()
			self.synchroniser.ready(self)
			self.state = self.WAIT_SCROLL

		elif self.state == self.WAIT_SCROLL:
			if not self.is_waiting():
				self.state = self.SCROLLING_SYNC

		elif self.state == self.SCROLLING_SYNC:
			if self.synchroniser.is_synchronised():
				self.synchroniser.busy(self)
				self.state = self.SCROLLING_WAIT

		elif self.state == self.SCROLLING_WAIT:
			if not self.is_waiting():
				self.state = self.SCROLLING

		elif self.state == self.SCROLLING:
			if self.image_x_pos < self.max_pos:
				self.render()
				self.image_x_pos += self.speed
			else:
				self.state = self.WAIT_SYNC
				
		elif self.state == self.WAIT_SYNC:
			if self.image_x_pos != 0:
				self.image_x_pos = 0
				self.render()
			else:
				if not self.is_waiting():
					self.Controller.cardChange(self, self.position + 1)
				
		

	def render(self):
		if(self.state == self.SCROLLING or self.state == self.WAIT_SYNC):
			self.IDestination.offset = (self.image_x_pos, 0)
		if(self.state == self.OPENING_SCROLL):
			self.IStaticOld.offset= (0,self.image_y_posA)
	
	def refresh(self):
		self.image_composition.remove_image(self.IDestination)
		self.image_composition.remove_image(self.IServiceNumber)
		self.image_composition.remove_image(self.IDisplayTime)
		self.image_composition.add_image(self.IDestination)
		self.image_composition.add_image(self.IServiceNumber)
		self.image_composition.add_image(self.IDisplayTime)


	def addPartner(self, partner):
		self.partner = partner

	def is_waiting(self):
		self.ticks += 1
		if self.ticks > self.delay:
			self.ticks = 0
			return False
		return True


#Board Controller
#Defines the board which controls what each off the lines in the display will show at any time
class boardFixed():
	def __init__(self, image_composition, scroll_delay, device):
		self.Services = LiveTime.GetData()   
		self.synchroniser = Synchroniser()
		self.scroll_delay = scroll_delay
		self.image_composition = image_composition
		self.device = device
		self.ticks = 0
		self.setInitalCards()
	
		NoServiceTemp = NoService(device, ImageFont.truetype("./lower.ttf",14))
		self.NoServices = ComposableImage(NoServiceTemp.image, position=(device.width/2- NoServiceTemp.width/2,device.height/2-NoServiceTemp.height/2))

		self.top.addPartner(self.middel)
		self.middel.addPartner(self.bottom)
	
	def setInitalCards(self):
		self.top = ScrollTime(image_composition, len(self.Services) >= 1 and self.Services[0] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 0, self)
		self.middel = ScrollTime(image_composition, len(self.Services) >= 2 and self.Services[1] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 1,self)
		self.bottom = ScrollTime(image_composition, len(self.Services) >= 3 and self.Services[2] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 2, self)
		self.x = len(self.Services) < 3 and len(self.Services) or 3

	def tick(self):
		if len(self.Services) == 0:
			self.image_composition.add_image(self.NoServices)
			if not self.is_waiting():
				self.Services = LiveTime.GetData()  
				self.setInitalCards()
				self.image_composition.remove_image(self.NoServices)
		else:
			self.top.tick()
			self.middel.tick()
			self.bottom.tick()
	
	def cardChange(self, card, row):
		#Need to fix when only one card can be found
		#Need to fix when less than the amount of cards you had before is found to remove old cards
		#Need to think about ordering properly.


		#card.changeCard(self.x < (len(self.Services)-1) and self.Services[self.x] or LiveTimeStud(),device)
		card.changeCard(self.Services[self.x % len(self.Services)],device)
		self.x = self.x + 1
		# or (math.ceil(self.x /3) > math.ceil(len(self.Services) / 3) and self.x%3 > (len(self.Services) %3))
		if self.x >= 9:
			self.Services = LiveTime.GetData()
			print("New Data")
			self.x = 0

	def is_waiting(self):
		self.ticks += 1
		if self.ticks > 100:
			self.ticks = 0
			return False
		return True
	
		
		
#Main
#Connects to the display and makes it update forever until ended by the user with a ctrl-c
serial = spi(device=0,port=0, bus_speed_hz=16000000)
device = ssd1322(serial_interface=serial, framebuffer="diff_to_previous",rotate=2)
image_composition = ImageComposition(device)
board = boardFixed(image_composition,30,device)


try:
	with canvas(device) as draw:
		draw.multiline_text((64, 10), "Departure Board", font= ImageFont.truetype("./Bold.ttf",20), align="center")
		draw.multiline_text((45, 35), "Version : 0.1.0  -  By Jonathan Foot", font=ImageFont.truetype("./Skinny.ttf",15), align="center")
	#time.sleep(2.5)

	while True:
		board.tick()
		time.sleep(0.025)
		FontTime = ImageFont.truetype("./time.otf",16)
		msgTime = str(datetime.now().strftime('%H:%M'))	
		with canvas(device, background=image_composition()) as draw:
			image_composition.refresh()
			draw.multiline_text(((device.width - draw.textsize(msgTime, FontTime)[0])/2, device.height-16), msgTime, font=FontTime, align="center")
except KeyboardInterrupt:
	pass