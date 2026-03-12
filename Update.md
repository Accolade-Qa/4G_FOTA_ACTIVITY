1. Read excel file of government server from the input folder and then take the server name and all firmware from the file and put it in the servers.json file 

2. update : for now if the queue is full from the serialreader then it puts the line as:
            12:40:16.130 [Thread-3] WARN  com.aepl.atcu.SerialReader - Processor Queue full: dropping line
                it should not be occured here.

3. for now program is checking the login packet and then have checks and then do the process but it gets updated the fota batch file and the web automation on each login packet it gets recieved. it should be like once the login packet gets recieved and processed and make the fota batch file and initiated the fota batch on web ui then it just have to monitor the fota batch file till the end like it should monitor for the download percentages till 100 % and then it should validate the next login packet 

4. for login packet it does have identification like:
|55AA,1,2,1719503665,861564061380138,89916420534724851291,ACON4NA082300092233,5.2.8_REL25,ACCDEV20222589462,UF,data.vahanshakti.in,4030,data.vahanshakti.in,4040,1,55555,1108,649,511,0,0,0,55555,1108,649,511,0,0,0.000000,-,0.000000,-,24.0,3.6,1,C,0,1,1|

    * negate the first and last '|' and the identification is on the third character like 2 whenever gets 2 at third character it is a login packet. and store only this packate and all other should be neglated.


