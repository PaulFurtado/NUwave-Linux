NUwave-Linux
============

A dirty script for automating the painful parts of connecting to Northeastern's
NUwave wireless network on Linux systems.

This should work on most systems which use NetworkManager to manage wireless
networks. It is intended to work with Python 2, so if you're using Arch
linux or another distribution which renamed the Python 2 binary to python2,
please alter the shebang at the beginning of this script appropriately.


NetworkManager Configuration
============================
Before executing this script, ensure that you have configured NUwave in
NetworkManger up to the point where it is capable of establishing a
connection to NUwave. To do this, ensure these settings are correct:
 - Wireless Security: "WPA & WPA2 Enterprise"
 - Authentication: "Protected EAP (PEAP)"
 - PEAP version: "Automatic"
 - CA Certificate: None
 - Inner Authentication: "MSCHAPv2"
 - Username: Your husky username without @husky.neu.edu
 - Password: Your husky password

After doing this, verify that /etc/NetworkManager/system-connections/NUwave
looks something like this:

    [ipv6]
    method=auto
    ip6-privacy=2

    [connection]
    id=NUwave
    uuid=<system specific>
    type=802-11-wireless

    [802-11-wireless-security]
    key-mgmt=wpa-eap

    [802-11-wireless]
    ssid=NUwave
    mode=infrastructure
    mac-address=<system specific>
    security=802-11-wireless-security

    [802-1x]
    eap=peap;
    identity=<your husky id>
    phase2-auth=mschapv2
    password-flags=1

    [ipv4]
    method=auto

What this script does
=====================

1. Temporarily disables Network Manager
   Why: The script performs a lot of operations which NetworkManager
        interferes with. Additionally, it needs to be restarted after
        altering its configuration file anyway.
2. Unloads the iwlwifi kernel module and reloads it with 11n_disable=1
   Why: For most people, NUwave does not work reliably with wireless N
        in linux.
3. Scans for all nearby access points and hard codes the BSSID of the
   access point with the best signal quality.
   Why: Hopping between access points results in disconnects for many
        people.
4. Re-enables NetworkManager

Note: This script doesn't actually connect to NUwave, it just configures the
      system correctly so you may still need to click NUwave in the network
      list after this script is complete.
