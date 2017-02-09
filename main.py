# -*- coding: utf-8 -*-
"""
Author: Stephen Wayne
Last Modified: 2/8/2017

This is a driver function for the philipsHue class. It will create a new
object that is tied to the physical Hue Bridge (if one is found), and it will
print updates to the terminal with initial bulb status as well as any updates
that may occur while the program is running (and updates that survive long
enough to be polled). It currently polls the lights every 2 seconds. It will
store the Bridge IP and its username in a text file so that it does not have
to reauthenticate every time it is run.
"""

import philipsHue
import time
import os.path

ip = None                            # IP and Username can be hard coded
user = None
filename = 'config.txt'              # file name to store IP and username


def poll_lights(Hue):
    ''' This function gets the status of all lights on the bridge every
    'poll_interval' seconds. We do this because there is no "push" or
    "interrupt" system with the Bridge API currently (as far as I know).
    '''
    num_lights = Hue.num_lights
    lights = Hue.lights
    for i in lights:                                    # check if light update
        Hue.update_light(int(i))
        num_lights = num_lights - 1
    if num_lights != 0:
        print('Error: not all lights were updated')
 

def get_bridge_data(filename):
    ''' This function gets the Bridge IP address and a username from a file in
    the root directory (currently named config.txt).
    '''
    global ip
    global user
    with open(filename, 'r') as f:
        read_data = f.read()
        f.close()
    
    idx_ip_start = len('IP:') + read_data.find('IP:')   # index of 1st char ip
    idx_ip_end = read_data.find(',username:')           # idx last char ip
    idx_user_start = idx_ip_end + len(',username:')     # idx 1st char username
    
    # if filename has an invalid format delete it
    if min(idx_ip_start, idx_ip_end, idx_user_start) == -1:
        print("%s is an invalid file. Reauthenticating..." % filename)
        ip = None
        user = None
        remove_config_file()
    else:
        ip = read_data[idx_ip_start:idx_ip_end]
        print("Connecting to Bridge at %s" % (ip))
        user = read_data[idx_user_start:len(read_data)]
        print("Using username %s" % (user))


def make_config_file(Hue):
    ''' This function writes the Bridge IP address and username to a file
    (named "config.txt" currently) to use in future runs to avoid
    reauthenticating each time the script is run (or hardcoding the values in).
    '''
    with open(filename, 'w') as f:
        f.write('IP:%s,username:%s' % (Hue.bridge_ip, Hue.username))


def remove_config_file():
    ''' If there is an issue with an existing configuration file delete it.
    '''
    os.remove(filename)


#

def main():
    ''' Driver function to monitor the bridge and print any light updates to
    terminal. Set the poll_interval variable to determine how quickly updates
    come in. In my testing (with 4 bulbs) in Spyder/Core i7 it uses about 0.1%
    CPU if polled every 2 seconds and slightly more if polled every second.
    Currently set to poll every 2 seconds.
    '''
    poll_interval = 2                          # seconds between polling bridge
    last_poll = time.time()                    # keep track of last poll
    
    if os.path.isfile(filename):               # if file w/ ip and username
        get_bridge_data(filename)              #      exists grab the data
        
    Hue = philipsHue.philipsHue(ip, user)      # instantiate bridge
    
    if Hue.update_file:                        # username was invalid
        remove_config_file()                   # delete file w/ invalid data
        
    if not os.path.isfile(filename):           # make the config file if it
        make_config_file(Hue)                  #      doesn't already exist

    # Poll the lights every poll_interval seconds    
    while True:
        if (time.time() - last_poll > poll_interval):
            poll_lights(Hue)
            last_poll = time.time()
        
        time.sleep(0.1*poll_interval)          # non blocking sleep
    
main()