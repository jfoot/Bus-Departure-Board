# Live Departure Board 
### Bus Departure Board for any UK Bus Stop
![Bus Demostartion Display](https://jonathanfoot.com/assets/DemoDisplay.gif)

### Train Departure Board for any UK Station
![Train Demostartion Display](https://jonathanfoot.com/assets/TrainDemoDisplay.gif)


Live Departure boards is a selection of different Python programs capable of replicating a live bus or rail departure board for any bus stop or train station (or tube station) in the UK. 

*Not all regions will provide live data and data quality may vary region to region. Some regions may charge for Live data, however, Scheduled/Timetabled data is free in all regions.*

## Project Resources

* Full information on how to use the programs can be found in the 
[project documentation](https://jonathanfoot.com/Projects/DepartureBoard/). 

* Full information on the parts you will need such as the SSD1322/ER-OLEDM032 display and Raspberry Pi, as well as how to set it up and install the programs can be found 
[on the project website](https://departureboard.jonathanfoot.com/)

## Programs Included

* Reading Buses Depature Board (ReadingBusesPy3.py)- get live bus stop information for all bus stops serviced by Reading Buses, this program uses the [Reading Buses API](https://reading-opendata.r2p.com/api-service)
* National Bus Depature Board (NationalBusesPy3.py)- get live bus stop infromation from any bus stop in the whole of the UK for all bus services, this program uses the [Transport API](http://transportapi.com)
* National Railway Depature Board (NationalRailPy3.py) - get live train station information for any UK train station, this program uses the [National Rail API](http://realtime.nationalrail.co.uk/OpenLDBWSRegistration/)
* London Underground Depature Board (LondonUndergroundPy3.py) - get live tube station information for any London Underground station, this program uses the [Transport for London API](https://api-portal.tfl.gov.uk/signup)

If you're still using the Python2 versions and would like to upgrade to Python3, instructions on doing so can be found at [update.jonathanfoot.com](https://update.jonathanfoot.com/).

If you're currently using an old version of the Reading Buses program that uses the old Reading Buses API and would like help changing to the new API please read the [help pages here](https://update2.jonathanfoot.com/)

If you're using an old version of Pillow (9 or lower), use the files in the /legacy/ folder instead.

## Bug Reporting
If you've found a bug and would like to report it please create a GitHub issue or send me an email about it and if I'm not to busy I will try to fix it.


## Example Video
[![Watch demostration video here](https://img.youtube.com/vi/9egAmw3UAvU/0.jpg)](https://www.youtube.com/watch?v=9egAmw3UAvU)