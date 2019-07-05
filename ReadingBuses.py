import urllib2
import time
import math
import os
import argparse
from PIL import ImageFont, Image, ImageDraw
from luma.core.render import canvas
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from lxml import objectify
from datetime import datetime, date
from luma.core.image_composition import ImageComposition, ComposableImage


##Start Up Paramarter Checks
#Checks value is greater than Zero.
def check_positive(value):
	try:
		ivalue = int(value)
		if ivalue <= 0:
			raise argparse.ArgumentTypeError("%s is invalid, vis invalid, value must be an integer value greater than 0." % value)
		return ivalue
	except:
		raise argparse.ArgumentTypeError("%s is invalid, value must be an integer value greater than 0." % value)

def check_time(value):
	try:
		datetime.strptime(value.split("-")[0], '%H:%M').time()
		datetime.strptime(value.split("-")[1], '%H:%M').time()
	except:
		raise argparse.ArgumentTypeError("%s is invalid, value must be in the form of XX:XX-YY:YY, where the values are in 24hr format." % value)
	return [datetime.strptime(value.split("-")[0], '%H:%M').time(),  datetime.strptime(value.split("-")[1], '%H:%M').time()]




parser = argparse.ArgumentParser(description='Reading Buses Live Departure Board, to run the program you will need to pass it all of the required paramters and you may wish to pass any optional paramters.')
#Defines all optional paramaters
parser.add_argument("-t","--TimeFormat", help="Do you wish to use 24hr or 12hr time format; default is 24hr.", type=int,choices=[12,24],default=24)
parser.add_argument("-v","--Speed", help="What speed do you want the text to scroll at on the display; default is 3, must be greater than 0.", type=check_positive,default=3)
parser.add_argument("-d","--Delay", help="How long the display will pause before starting the next animation; default is 30, must be greater than 0.", type=check_positive,default=30)
parser.add_argument("-r","--RecoveryTime", help="How long the display will wait before attempting to get new data again after previously failing; default is 100, must be greater than 0.", type=check_positive,default=100)
parser.add_argument("-n","--NumberOfCards", help="The maximum number of cards you will see before forcing a new data retrieval, a limit is recommend to prevent cycling through data which may become out of data or going too far into scheduled buses; default is 9, must be greater than 0.", type=check_positive,default=100)
parser.add_argument("-x","--Rotation", help="Defines which way up the screen is rendered; default is 2", type=int,default=2,choices=[0,2])
parser.add_argument("-l","--RequestLimit", help="Defines the minium amount of time the display must wait before making a new data request; default is 55(seconds)", type=check_positive,default=55)
parser.add_argument("-z","--StaticUpdateLimit", help="Defines the amount of time the display will wait before updating the expected arrival time (based upon it's last known predicted arrival time); defualt is  15(seconds), this should be lower than your 'RequestLimit'", type=check_positive,default=15)
parser.add_argument("-e","--EnergySaverMode", help="To save screen from burn in and prolong it's life it is recommend to have energy saving mode enabled. 'off' is default, between the hours set the screen will turn off. 'dim' will turn the screen brightness down, but not completely off. 'none' will do nothing and leave the screen on; this is not recommend, you can change your active hours instead.", type=str,choices=["none","dim","off"],default="off")
parser.add_argument("-i","--InactiveHours", help="The peroid of time for which the display will go into 'Energy Saving Mode' if turned on; default is '23:00-07:00'", type=check_time,default="23:00-07:00")
parser.add_argument("-u","--UpdateDays", help="The number of days for which the Pi will wait before rebooting and checking for a new update again during your energy saving period; defualt 3 days.", type=check_positive, default=3)
parser.add_argument("--ReducedAnimations", help="If you wish to stop the Via animation and cycle faster through the services use this tag to turn the animation off.", dest='ReducedAnimations', action='store_true')
parser.add_argument("--UnfixNextToArrive",dest='FixToArrive', action='store_false', help="Keep the bus sonnest to next arrive at the very top of the display until it has left; by default true")
parser.add_argument("--HideUnknownVias", help="If the API does not report any known via route a placeholder of 'Via Central Reading' is used. If you wish to stop the animation for unknowns use this tag.", dest='HideUnknownVias', action='store_true')
parser.add_argument('--no-splashscreen', dest='SplashScreen', action='store_false',help="Do you wish to see the splash screen at start up; recommended and on by default.")
parser.add_argument('--ShowIndex', dest='ShowIndex', action='store_true',help="Do you wish to see index position for each service due to arrive.")



#Defines the required paramaters
requiredNamed = parser.add_argument_group('required named arguments')
requiredNamed.add_argument("-k","--APIKey", help="Your Reading Buses API Key, you can get your own from: http://rtl2.ods-live.co.uk/cms/apiservice", type=str,required=True)
requiredNamed.add_argument("-s","--StopID", help="The Naptan Code for the specific bus stop you wish to display.", type=str,required=True)
Args = parser.parse_args()
BasicFont = ImageFont.truetype("./lower.ttf",14)
GenericVia = "Via Central Reading"

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
		self.ID =  "0"
	
	def TimePassedStatic(self):
		return False
		
	
#Used to get live data from the Reading Buses API.
class LiveTime(object):
	LastUpdate = datetime.now()

	def __init__(self, Data, Index):
		self.ServiceNumber = "%s.%s" % (Index + 1, str(Data.LineRef)) if Args.ShowIndex else str(Data.LineRef)
		self.Destination = str(Data.DestinationName)
		self.SchArrival = str(Data.MonitoredCall.AimedArrivalTime).split("+")[0]
		self.ExptArrival = str(getattr( Data.MonitoredCall, "ExpectedArrivalTime", "")).split("+")[0]
		self.Via = str(getattr(Data, "Via", GenericVia))
		self.DisplayTime = self.GetDisplayTime()
		self.ID =  str(Data.FramedVehicleJourneyRef.DatedVehicleJourneyRef)
		self.LastStaticUpdate = datetime.now()

	#Returns the value to display the time on the board.
	def GetDisplayTime(self):
		self.LastStaticUpdate = datetime.now()
		if self.ExptArrival == "":
			return " " + datetime.strptime(self.SchArrival, '%Y-%m-%dT%H:%M:%S').strftime("%H:%M" if (Args.TimeFormat==24) else  "%I:%M")
		else:
			Diff =  (datetime.strptime(self.ExptArrival, '%Y-%m-%dT%H:%M:%S') - datetime.now()).total_seconds() / 60
			if Diff <= 2:
				return ' Due'
			if Diff >=15 :
				return ' ' + datetime.strptime(self.SchArrival, '%Y-%m-%dT%H:%M:%S').strftime("%H:%M" if (Args.TimeFormat==24) else  "%I:%M")
			return  ' %d min' % Diff

	@staticmethod
	def TimePassed():
		return (datetime.now() - LiveTime.LastUpdate).total_seconds() > Args.RequestLimit

	def TimePassedStatic(self):
		return ("min" in self.DisplayTime) and (datetime.now() - self.LastStaticUpdate).total_seconds() > Args.StaticUpdateLimit 


	#Used to actually get the data from the API
	@staticmethod
	def GetData():
		LiveTime.LastUpdate = datetime.now()
		services = []

		try:
			raw = urllib2.urlopen("https://rtl2.ods-live.co.uk/api/siri/sm?key=%s&location=%s" % (Args.APIKey, Args.StopID)).read()
			rawServices = objectify.fromstring(raw)
		
			#Makes sure the same service isn't got multiple times.
			for root in rawServices.ServiceDelivery.StopMonitoringDelivery.MonitoredStopVisit:
				service = root.MonitoredVehicleJourney
				exsits = False
				for current in services:
					if current.ID == service.FramedVehicleJourneyRef.DatedVehicleJourneyRef:
						exsits = True
						break

				if exsits == False:
					services.append(LiveTime(service, len(services)))
			return services
		except Exception as e:
			print(str(e))
			return []


###
# Below contains everything for the drawing and animating of the board.
###

#Used to create the time and service number on the board
class TextImage():
	def __init__(self, device, text):
		self.image = Image.new(device.mode, (device.width, 16))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), text, font=BasicFont, fill="white")
	
		self.width = 5 + draw.textsize(text, BasicFont)[0]
		self.height = 5 + draw.textsize(text, BasicFont)[1]
		del draw

#Used to create the destination and via board.
class TextImageComplex():
	def __init__(self, device, destination, via, startOffset):
		self.image = Image.new(device.mode, (device.width*2, 16))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), destination, font=BasicFont, fill="white")
		draw.text((device.width - startOffset, 0), via, font=BasicFont, fill="white")
			
		self.width = device.width + draw.textsize(via, BasicFont)[0]  - startOffset
		self.height = 16
		del draw

#Used for the opening animation, creates a static two lines of the new and previous service.
class StaticTextImage():
	def __init__(self, device, service, previous_service):			
		self.image = Image.new(device.mode, (device.width, 32))
		draw = ImageDraw.Draw(self.image)
		displayTimeTempPrevious = TextImage(device, previous_service.DisplayTime)
		displayTimeTemp = TextImage(device, service.DisplayTime)

		draw.text((0, 16), service.ServiceNumber, font=BasicFont, fill="white")
		draw.text((device.width - displayTimeTemp.width, 16), service.DisplayTime, font=BasicFont, fill="white")
		draw.text((45 if Args.ShowIndex else 30, 16), service.Destination, font=BasicFont, fill="white")	

		draw.text((45 if Args.ShowIndex else 30, 0), previous_service.Destination, font=BasicFont, fill="white")	
		draw.text((0, 0), previous_service.ServiceNumber, font=BasicFont, fill="white")
		draw.text((device.width - displayTimeTempPrevious.width, 0), previous_service.DisplayTime, font=BasicFont, fill="white")
	
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

#Error message displayed when no data can be found.
class NoService():
	def __init__(self, device):		
		w = device.width
		h = 16
		msg = "No Scheduled Services Found"
		self.image = Image.new(device.mode, (w, h))
		draw = ImageDraw.Draw(self.image)
		draw.text((0, 0), msg, font=BasicFont, fill="white")
	
		self.width = draw.textsize(msg, font=BasicFont)[0]
		self.height = draw.textsize(msg, font=BasicFont)[1]
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
	SCROLL_DECIDER = 3
	SCROLLING_WAIT = 4
	SCROLLING = 5
	WAIT_SYNC = 6

	WAIT_STUD = 7
	STUD_SCROLL = 8
	STUD_END = 9

	STUD = -1
	
	def __init__(self, image_composition, service, previous_service, scroll_delay, synchroniser, device, position, controller):
		self.speed = Args.Speed
		self.position = position
		self.Controller = controller
		
		self.image_composition = image_composition
		self.rectangle = ComposableImage(RectangleCover(device).image, position=(0,16 * position + 16))
		self.CurrentService = service
		
		self.generateCard(service)
		
		self.IStaticOld =  ComposableImage(StaticTextImage(device,service, previous_service).image, position=(0, (16 * position)))
		
		self.image_composition.add_image(self.IStaticOld)
		self.image_composition.add_image(self.rectangle)
		
		self.max_pos = self.IDestination.width
		self.image_y_posA = 0
		self.image_x_pos = 0
		self.device = device
		self.partner = None
			
		self.delay = scroll_delay
		self.ticks = 0
		self.state = self.OPENING_SCROLL if service.ID != 0 else self.STUD
		self.synchroniser = synchroniser
		self.render()
		self.synchroniser.ready(self)

	def generateCard(self,service):
		displayTimeTemp = TextImage(device, service.DisplayTime)
		IDestinationTemp  = TextImageComplex(device, service.Destination,service.Via, displayTimeTemp.width)

		self.IDestination =  ComposableImage(IDestinationTemp.image.crop((0,0,IDestinationTemp.width + 10,16)), position=(45 if Args.ShowIndex else 30, 16 * self.position))
		self.IServiceNumber =  ComposableImage(TextImage(device, service.ServiceNumber).image.crop((0,0,45 if Args.ShowIndex else 30,16)), position=(0, 16 * self.position))
		self.IDisplayTime =  ComposableImage(displayTimeTemp.image, position=(device.width - displayTimeTemp.width, 16 * self.position))

	def updateCard(self, newService, device):
		self.state = self.SCROLL_DECIDER
		self.synchroniser.ready(self)
		self.image_composition.remove_image(self.IDisplayTime)

		displayTimeTemp = TextImage(device, newService.DisplayTime)
		self.IDisplayTime = ComposableImage(displayTimeTemp.image, position=(device.width - displayTimeTemp.width, 16 * self.position))
	
		self.image_composition.add_image(self.IDisplayTime)
		self.image_composition.refresh()


	def changeCard(self, newService, device):
		if newService.ID == "0" and self.CurrentService.ID == "0":
			self.state = self.STUD
			self.synchroniser.ready(self)
			return 
			
		self.synchroniser.busy(self)
		self.IStaticOld =  ComposableImage(StaticTextImage(device,newService, self.CurrentService).image, position=(0, (16 * self.position)))
	
		self.image_composition.add_image(self.IStaticOld)
		self.image_composition.add_image(self.rectangle)
		self.image_composition.remove_image(self.IDestination)
		self.image_composition.remove_image(self.IServiceNumber)
		self.image_composition.remove_image(self.IDisplayTime)
		if self.partner != None and self.partner.CurrentService.ID != "0":
			self.partner.refresh()
			
		self.image_composition.refresh()
		del self.IDestination
		del self.IServiceNumber
		del self.IDisplayTime

		self.generateCard(newService)
		self.CurrentService = newService
		self.max_pos = self.IDestination.width
		
		self.state = self.WAIT_STUD if (newService.ID == "0") else self.WAIT_OPENING
		
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
		self.image_composition.refresh() 

	def tick(self):
		#Update X min till arrival.
		if self.CurrentService.TimePassedStatic() and (self.state == self.SCROLL_DECIDER or self.state == self.SCROLLING_WAIT or self.state == self.SCROLLING or self.state == self.WAIT_SYNC):
			self.image_composition.remove_image(self.IDisplayTime)
			self.CurrentService.DisplayTime = self.CurrentService.GetDisplayTime()
			displayTimeTemp = TextImage(device, self.CurrentService.DisplayTime)
			self.IDisplayTime = ComposableImage(displayTimeTemp.image, position=(device.width - displayTimeTemp.width, 16 * self.position))           
			self.image_composition.add_image(self.IDisplayTime)
			self.image_composition.refresh()


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
			self.state = self.SCROLL_DECIDER

		elif self.state == self.SCROLL_DECIDER:
			if self.synchroniser.is_synchronised():
				if not self.is_waiting():
					if self.synchroniser.is_synchronised():
						self.synchroniser.busy(self)
						if (Args.HideUnknownVias and self.CurrentService.Via == GenericVia) or Args.ReducedAnimations:
							self.state = self.WAIT_SYNC
						elif self.CurrentService.ID == "0":
							self.synchroniser.ready(self)
							self.state = self.STUD
						else:
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
					self.Controller.requestCardChange(self, self.position + 1)


		elif self.state == self.WAIT_STUD:
			if not self.is_waiting():
				self.state = self.STUD_SCROLL
		elif self.state == self.STUD_SCROLL:
			if self.image_y_posA < 16:              
				self.render()
				self.image_y_posA += self.speed
			else:
				self.state = self.STUD_END

		elif self.state == self.STUD_END:
			self.image_x_pos = 0
			self.image_y_posA = 0
			self.image_composition.remove_image(self.IStaticOld)
			self.image_composition.remove_image(self.rectangle)
			del self.IStaticOld
			del self.rectangle

			self.render()
			self.synchroniser.ready(self)
			self.state = self.STUD
		elif self.state == self.STUD:
			if not self.is_waiting():
				self.Controller.requestCardChange(self, self.position + 1)
			
		

	def render(self):
		if(self.state == self.SCROLLING or self.state == self.WAIT_SYNC):
			self.IDestination.offset = (self.image_x_pos, 0)
		if(self.state == self.OPENING_SCROLL or self.state == self.STUD_SCROLL):
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
	
		NoServiceTemp = NoService(device)
		self.NoServices = ComposableImage(NoServiceTemp.image, position=(device.width/2- NoServiceTemp.width/2,device.height/2-NoServiceTemp.height/2))

		self.top.addPartner(self.middel)
		self.middel.addPartner(self.bottom)
	
	def __del__(self):
		del self.top
		del self.middel
		del self.bottom
		self.image_composition.refresh()


	#Set up the cards for the inital starting animation.
	def setInitalCards(self):
		self.top = ScrollTime(image_composition, len(self.Services) >= 1 and self.Services[0] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 0, self)
		self.middel = ScrollTime(image_composition, len(self.Services) >= 2 and self.Services[1] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 1,self)
		self.bottom = ScrollTime(image_composition, len(self.Services) >= 3 and self.Services[2] or LiveTimeStud(),LiveTimeStud(), self.scroll_delay, self.synchroniser, device, 2, self)
		self.x = len(self.Services) < 3 and len(self.Services) or 3

	def tick(self):
		#If no data can be found.
		if len(self.Services) == 0:
			self.image_composition.add_image(self.NoServices)
			#Wait a peroid of time then try getting new data again.
			if not self.is_waiting():
				self.Services = LiveTime.GetData()  
				self.setInitalCards()
				self.image_composition.remove_image(self.NoServices)
		else:
			self.top.tick()
			self.middel.tick()
			self.bottom.tick()
	
	def requestCardChange(self, card, row):
		if (self.x > Args.NumberOfCards or self.x >len(self.Services)-1):
			self.x = 1 if Args.FixToArrive else 0
			if LiveTime.TimePassed():  
				self.Services = LiveTime.GetData()
				print("New Data Retrieved %s" % datetime.now().time())

		if row > len(self.Services):       
			card.changeCard(LiveTimeStud(),device)
			return

		if len(self.Services) <= 3:
			if self.Services[row-1].ID == card.CurrentService.ID:
				card.updateCard(self.Services[row-1],device)
			else:
				card.changeCard(self.Services[row-1],device)
		else:
			if Args.FixToArrive and row == 1:
				if self.Services[0].ID == card.CurrentService.ID:
					card.updateCard(self.Services[0],device)
				else:
					card.changeCard(self.Services[0],device)
			else:
				if self.Services[self.x % len(self.Services)].ID == card.CurrentService.ID:
					card.updateCard(self.Services[self.x % len(self.Services)],device)
				else:
					card.changeCard(self.Services[self.x % len(self.Services)],device)
		
		if  not (Args.FixToArrive and row == 1):
			self.x = self.x + 1



	def is_waiting(self):
		self.ticks += 1
		if self.ticks > Args.RecoveryTime:
			self.ticks = 0
			return False
		return True
	
		


def is_time_between():
	# If check time is not given, default to current UTC time
	check_time = datetime.now().time()
	if Args.InactiveHours[0] < Args.InactiveHours[1]:
		return check_time >= Args.InactiveHours[0] and check_time <= Args.InactiveHours[1]
	else: # crosses midnight
		return check_time >= Args.InactiveHours[0] or check_time <= Args.InactiveHours[1]



#Main
#Connects to the display and makes it update forever until ended by the user with a ctrl-c
serial = spi(device=0,port=0, bus_speed_hz=16000000)
device = ssd1322(serial_interface=serial, framebuffer="diff_to_previous",rotate=Args.Rotation)
image_composition = ImageComposition(device)
board = boardFixed(image_composition,Args.Delay,device)
FontTime = ImageFont.truetype("./time.otf",16)
device.contrast(255)
energyMode = "normal"
StartUpDate = datetime.now().date()

def display():
	board.tick()
	msgTime = str(datetime.now().strftime("%H:%M" if (Args.TimeFormat==24) else "%I:%M"))	
	with canvas(device, background=image_composition()) as draw:
		image_composition.refresh()
		draw.multiline_text(((device.width - draw.textsize(msgTime, FontTime)[0])/2, device.height-16), msgTime, font=FontTime, align="center")

def Splash():
	if Args.SplashScreen:
		with canvas(device) as draw:
			draw.multiline_text((64, 10), "Departure Board", font= ImageFont.truetype("./Bold.ttf",20), align="center")
			draw.multiline_text((45, 35), "Version : 1.0.RB -  By Jonathan Foot", font=ImageFont.truetype("./Skinny.ttf",15), align="center")
		time.sleep(2.5)

try:

	Splash()

	while True:
		time.sleep(0.02)
		if Args.EnergySaverMode != "none" and is_time_between():
			if (datetime.now().date() - StartUpDate).days >= Args.UpdateDays:
				print "Restarting Pi To Check For Updates On Start Up."
				os.system("sudo reboot")
			if Args.EnergySaverMode == "dim":
				if energyMode == "normal":
					device.contrast(15)
					energyMode = "dim"
				display()
			elif Args.EnergySaverMode == "off":
				if energyMode == "normal":
					del board
					device.hide()
					energyMode = "off"      
		else:
			if energyMode != "normal":
				device.contrast(255)
				if energyMode == "off":
					device.show()
					Splash()
					board = boardFixed(image_composition,Args.Delay,device)
				energyMode = "normal"
			display()
except KeyboardInterrupt:
	pass
