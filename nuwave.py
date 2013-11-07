#!/usr/bin/python

"""
    A dirty script for automating the painful parts of connecting to
    Northeastern's NUwave wireless network on Linux systems.
"""

import os
import subprocess
import sys
import time

# Directory containing the Network Manager system-wide wifi connections.
NETMAN_SYS_CONNS = '/etc/NetworkManager/system-connections/'

def _get_networks(interface):
    """
        Gets a dict mapping SSIDs to lists of dicts containing access point
        BSSID and signal quality.
    """
    iw_cmd = ['iwlist', interface, 'scanning']
    pipe = subprocess.PIPE
    proc = subprocess.Popen(iw_cmd, stdout=pipe, stderr=pipe)
    stdout, stderr = proc.communicate()
    if stderr.strip():
        raise Exception('iwlist error:\n%s' % stderr.strip())
    # net_map contains the information about each SSID. The keys are the SSID
    # of the wireless network and the values are a list of dicts containing
    # the AP information.
    net_map = {}
    # The keys needed in the dict to consider information about this access
    # point to be complete
    reqd_keys = ('bssid', 'quality', 'ssid')
    cur_info = {}
    # Parse the lines of output
    for line in stdout.split('\n'):
        if 'Cell' in line and 'Address' in line:
            cur_info = {'bssid': line.strip().split()[-1]}
        elif cur_info and 'Quality=' in line:
            qualstr = line.partition('=')[2].partition(' ')[0]
            numerator, denominator = tuple(qualstr.split('/'))
            cur_info['quality'] = float(numerator) / float(denominator) * 100
        elif cur_info and 'ESSID:' in line:
            cur_info['ssid'] = line.partition(':')[2].strip().strip('"')

        if cur_info and all(k in cur_info for k in reqd_keys):
            ssid = cur_info['ssid']
            del cur_info['ssid']
            if ssid not in net_map:
                net_map[ssid] = []
            net_map[ssid].append(cur_info)
            cur_info = {}
    # Sort each AP list by quality
    for ap_list in net_map.itervalues():
        ap_list.sort(key=lambda netinfo: -1 * netinfo['quality'])
    return net_map

def get_networks(iface):
    """
        Calls _get_networks with retries. Retries are necessary because the
        interface may be temporarily busy due to NetworkManager doing its own
        scans or since we may have just restared the interface,
        it may not be ready to perform a scan yet.
    """
    for i in range(30):
        try:
            return _get_networks(iface)
        except (Exception), err:
            errstr = str(err)
            if 'Network is down' in errstr or \
                "doesn't support scanning" in errstr:
                print 'Network is down, retrying.'
                time.sleep(1)
            elif 'Device or resource busy' in errstr:
                print 'Interface is busy, retrying.'
                time.sleep(1)
            else:
                raise
    raise Exception('Interface did not come up.')

def checked_cmd(cmd):
    """
        Runs a command using subprocess.Popen and returns its stdout. Raises an
        exception if the process exits with a return code other than 0 or there
        is any output to stderr which isn't whitespace.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0 or stderr.strip():
        raise Exception('CMD (%s) error: "%s"' % (cmd, stderr))
    return stdout

def netman_cmd(args):
    """
        Convenience function for calling "nmcli" commands via checked_cmd
    """
    return checked_cmd(['nmcli'] + args)

def update_bssid(network, bssid):
    """
        Updates the BSSID in the network manager config file for the network
    """
    path = os.path.join(NETMAN_SYS_CONNS, network)
    with open(path, 'r') as fobj:
        contents = fobj.read()
    if '\nbssid=' in contents:
        start = contents.index('\nbssid=') + 7
        end = contents.index('\n', start)
        contents = contents[:start] + bssid + contents[end:]
    else:
        contents = contents.replace('[802-11-wireless]',
            '[802-11-wireless]\nbssid=%s' % bssid)
    with open(path, 'w') as fobj:
        fobj.write(contents)

def print_netmap(net_map):
    """
        Pretty-prints the network dict returned by get_networks
    """
    ssids = net_map.keys()
    ssids.sort()
    for ssid in ssids:
        print 'SSID: %s' % ssid
        for apinfo in net_map[ssid]:
            signal = apinfo['quality']
            ipart, dpart = tuple(str(signal).split('.'))
            dpart = dpart.ljust(2, '0')[:2]
            print '    %s.%s%% - %s' % (ipart, dpart, apinfo['bssid'])

def disable_11n():
    """
        Reloads the iwlifi kernel module disabling 802.11n
    """
    proc = subprocess.Popen(['modprobe', '-r', 'iwlwifi'])
    proc.wait()
    if proc.returncode != 0:
        raise Exception('Error removing module iwlwifi')
    proc = subprocess.Popen(['modprobe', 'iwlwifi', '11n_disable=1'])
    proc.wait()
    if proc.returncode != 0:
        raise Exception('Error reloading iwlwifi with 11n_disable=1')

def connect_nuwave(interface):
    print 'Temporarily disabling wifi'
    try:
        netman_cmd(['nm', 'enable', 'false'])
    except (Exception), err:
        if 'Already disabled' not in str(err):
            raise
    print 'Disabling 802.11n since it is buggy with NUwave and Linux'
    disable_11n()
    print 'Manually enabling "%s"' % interface
    for i in range(30):
        try:
            checked_cmd(['ifconfig', interface, 'up'])
            break
        except (Exception), err:
            errstr = str(err)
            if 'RF-kill' in errstr or 'No such device' in errstr:
                time.sleep(1)
            else:
                raise
    print 'Scanning for access points on %s' % interface
    net_map = get_networks(interface)
    if 'NUwave' not in net_map:
        raise Exception('NUwave not found!')
    ap = net_map['NUwave'][0]
    print 'Updating BSSID to: %s' % ap['bssid']
    update_bssid('NUwave', ap['bssid'])
    print 'Re-enabling NetworkManager'
    netman_cmd(['nm', 'enable', 'true'])

def main():
    """
        Handles arguments and executes appropriate function.
    """
    args = sys.argv[1:]
    if not args:
        print '''
    Commands:
        list [interface] - Lists access points and signal quality.
        nuwave - Connects to the best NUwave server
        '''
    elif args[0] == 'list':
        if len(args) > 1:
            iface = args[1]
        else:
            iface = 'wlan0'
        print_netmap(get_networks(iface))
    elif args[0] == 'nuwave':
        if len(args) > 1:
            iface = args[1]
        else:
            iface = 'wlan0'
        connect_nuwave(iface)

if __name__ == '__main__':
    main()
