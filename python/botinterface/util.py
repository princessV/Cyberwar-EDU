'''
Created on Feb 18, 2017

@author: sethjn
'''

import md5

def FingerPrint(data):
    return md5.new(data).hexdigest()

def InsertChecksum(packet, password=""):
    packet.Checksum = password
    checksum = FingerPrint(packet.__serialize__())
    packet.Checksum = checksum
    
def VerifyChecksum(packet, password=""):
    verifyChecksum = packet.Checksum
    packet.Checksum = password
    checksum = FingerPrint(packet.__serialize__())
    packet.Checksum = verifyChecksum
    return verifyChecksum == checksum