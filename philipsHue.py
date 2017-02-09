# -*- coding: utf-8 -*-
"""
Author: Stephen Wayne
Last Modified: 2/8/2017

This is a class to get basic data from the Philips Hue API.
"""

import sys
import requests as r               # HTTP for humans
import json
import time

class philipsHue:
    CONFIG_FILE = "config.txt"
    bridge_ip = None
    username = None
    lights = {}
    light_ids = []
    num_lights = 0
    timeout = 15                   # time to wait for user to press link button
    update_file = False


    def __init__(self, bridge_ip_addr = None, username = None):
        ''' This function initializes the Hue Bridge. If an IP address and/or
        username are provided it will use those. If no IP provided it will scan
        the network to find the Bridge IP. If no username is provided it will
        ask the user to press the button on the bridge and create a new
        username.
        '''
        if bridge_ip_addr is None:             # get ip address of Hue Bridge
            self.get_bridge_ip()
        else:                                  # validate and update IP addr
            if self.validate_ip(bridge_ip_addr):
                self.bridge_ip = bridge_ip_addr
            else:
                self.get_bridge_ip()
                self.update_file = True
    
        if username is None:                   # get a username for Huge Bridge
            self.get_username()
        else:                                  # validate and update username
            if self.validate_user(username):
                self.username = username
            else:
                self.get_username()
                self.update_file = True

        self.get_lights()                       # get status of all lights
        print("Printing initial lights relevant state information:")
        self.print_light_status()               # print initial light status


    def get_bridge_ip(self):
        ''' This function finds the IP address of a Hue bridge on the network.
        If there is an error getting a response the program will exit with an
        error msg. It gets the json response and reads the "internalipaddress"
        section. It is safe to assume only one Bridge will be connected for
        this challenge. Only call this if Bridge IP address isn't known.
        '''
        addr = 'https://www.meethue.com/api/nupnp'
        response = self.get_response(addr)
        # Verify that a response was received
        if not response.json():
            sys.exit("No Hue Bridge found on current network. Program exit.")
            
        if response.raise_for_status() is None: # successful request
            response = response.json()[0]
        else:                                   # failed request
            sys.exit("Cannot read Hue Bridge IP Address")

        self.bridge_ip = response["internalipaddress"]
        print("Found Bridge at %s" % self.bridge_ip)


    def get_username(self):
        ''' This function obtains a new username from the Hue Bridge. It
        requires that the user press the button on the Hue Bridge if no
        username is given in 'config.txt' (in the root directory). Time out if
        the button is not pressed in [currently] 15 seconds.
        '''
        addr = 'http://%s/api' % (self.bridge_ip)
        payload = {'devicetype':'my_hue_script'}
        
        try:
            response = r.post(addr, json=payload).json()[0]
        except r.exceptions.ConnectionError:
            r.status_code = ("No response received from Bridge. Ensure that "
                             "it is connected to power and network and "
                             "functioning properly. Program exit.")
            sys.exit(r.status_code)
            
        now = time.time()
        # get username from Hue Bridge or time out trying!
        if 'error' in response:
            if 'link button not pressed' in response['error']['description']:
                print('Please press the link button on the Hue Bridge.')
                
                while 'error' in response and (time.time()-now) < self.timeout:
                    response = r.post(addr, json=payload).json()[0]
                    time.sleep(0.2)
        
        if 'success' in response:
            if 'username' in response['success']:
                self.username = response['success']['username']
                print("Obtained username: %s" % (self.username))
            else:
                sys.exit("No username obtained from Bridge. Program exit.")
        else:
            sys.exit("No username obtained from Bridge. Program exit.")


    def validate_ip(self, ip):
        ''' This function checks to see if there is a response at the given
        Hue Bridge ip address. If the IP is valid the function returns true,
        else false.
        '''
        addr = 'http://%s' % ip
        
        try:
            r.get(addr)
            return True
        except r.exceptions.ConnectionError:
            s = ("No response from Bridge at %s. Finding new Bridge..." % ip)
            print(s)
            return False


    def validate_user(self, user):
        ''' This function takes the username and checks if it is valid. If it
        is not valid it will indicate this by returning false. If the username
        is valid it will return true.
        '''
        addr = 'http://%s/api/%s/' % (self.bridge_ip, user)
        response = self.get_response(addr)
        
        # kinda hacky but response length varies and we just need to check
        # if there was an error or not
        if response.raise_for_status() is None:
            if len(response.json()) == 1:
                response = response.json()[0]
            else:
                response = response.json()
        else:
            sys.exit("Error validating user. Program exit.")

        # if there was an error indicate that and get new username
        if 'error' in response:
            if 'unauthorized user' in response['error']['description']:
                print("Invalid username. Getting new username...")
                return False
            else:
                sys.exit("Error when validating username. Program exit")
        else:
            return True


    def get_lights(self):
        ''' This function finds all lights connected to the Bridge at bridge_ip
        and puts the relevant information (name, id, on, brightness, reachable)
        into the object.
        '''
        addr = 'http://%s/api/%s/lights' % (self.bridge_ip, self.username)
        response = self.get_response(addr)
            
        if response.raise_for_status() is None:
            response = response.json()
        else:
            sys.exit("Error reading lights on bridge" + str(self.bridge_ip))

        self.num_lights = len(response)     # #items in response = #lights
        self.light_ids = sorted(response.keys())

        for i in self.light_ids:            # loop through lights on Bridge
            jsonStr = json.JSONEncoder().encode({
                i:{
                'name':       response[i]['name'],
                'reachable':  response[i]['state']['reachable'],
                'id':         i,
                'on':         response[i]['state']['on'],
                'brightness': self.calc_brightness(response[i]['state']['bri'])
                }
            })
            self.lights[i] = jsonStr


    def update_light(self, light_id):
        ''' This will update the data for just a single light (light_id) if the
        device is reachable. Note that the Bridge requires a few seconds to
        realize that a bulb has become unreachable (if it is unplugged, for
        example), or to recognize that an unreachable bulb has become
        reachable. It seems to recognize the latter transition faster than the
        former. I tested the delay on my phone...it's a Hue thing. Surprisingly
        if a light is unplugged and plugged back in within a second or so it
        will sometimes maintain a connection to the Bridge and update status.
        '''
        if str(light_id) not in self.light_ids:        # make sure input valid
            sys.exit(str(light_id) + ' is not a valid light. Program exit.')

        curr_light = json.loads(self.lights[str(light_id)])
        change_flag = False
        
        # Check current status of light_id. Exit program if no response
        addr = 'http://%s/api/%s/lights/%d' % (self.bridge_ip, self.username,
                                               light_id)
        response = self.get_response(addr)
        
        if response.raise_for_status() is None:        # if no error reading
            response = response.json()                 # get light_id's data
        else:
            sys.exit("error reading light id " + light_id)

        reachable = response['state']['reachable']
        # Make sure light is reachable before we try to update values
        if reachable:
            tmp_bri = self.calc_brightness(response['state']['bri'])
            tmp_name = response['name']
            tmp_on = response['state']['on']

            # Check if parameters have changed. Update and pretty print if so
            if reachable != curr_light[str(light_id)]['reachable']:
                change_flag = True
                curr_light[str(light_id)]['reachable'] = reachable
                msg = {'id': light_id, 'reachable': reachable}
                print(json.dumps(msg, indent=4))
            
            if tmp_bri != curr_light[str(light_id)]['brightness']:
                change_flag = True
                curr_light[str(light_id)]['brightness'] = tmp_bri
                msg = {'id': light_id, ' brightness': tmp_bri}
                print(json.dumps(msg, indent=4))
            
            if tmp_name != curr_light[str(light_id)]['name']:
                change_flag = True
                curr_light[str(light_id)]['name'] = tmp_name
                msg = {'id': light_id, 'name': tmp_name}
                print(json.dumps(msg, indent=4))
                
            if tmp_on != curr_light[str(light_id)]['on']:
                change_flag = True
                curr_light[str(light_id)]['on'] = tmp_on
                msg = {'id': light_id, 'on': tmp_on}
                print(json.dumps(msg, indent=4))
            
            if change_flag:           # update object on parameter change
                self.lights[str(light_id)] = json.dumps(curr_light)
        # if light is unreachable we update that parameter and notify
        else:
            if reachable != curr_light[str(light_id)]['reachable']:
                print('Light %d unreachable. Data may be wrong.' % light_id)
                curr_light[str(light_id)]['reachable'] = reachable
                self.lights[str(light_id)] = json.dumps(curr_light)


    def get_response(self, addr):
        ''' This uses the http get function from python requests with some
        error checking added in case the Bridge becomes unresponsive.
        Returns the http get response if the request was successful.
        '''
        try:
            response = r.get(addr)
        except r.exceptions.ConnectionError:
            r.status_code = ("No response received from Bridge. Ensure that "
                             "it is connected to power and network and "
                             "functioning properly. Program exit.")
            sys.exit(r.status_code)
        
        return response


    def calc_brightness(self, bri):
        ''' We want brightness to be represented as an integer between 0 and
        100. Hue Bridge reports brightness as an integer between 1 and 254, so
        we must rescale.
        '''
        brightness = round(100 * (bri - 1) / 253)     # round to closest int
        return brightness


    def print_light_status(self):
        ''' This function pretty prints the current status (id, bri, name, on,
        reachable) of all lights connected to the Hue Bridge
        '''
        for light in self.light_ids:
            json_str = json.loads(self.lights[light])
            json_formatted = json.dumps(json_str, indent=4)
            print(json_formatted)