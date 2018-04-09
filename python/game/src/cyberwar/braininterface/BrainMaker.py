'''
Created on Apr 4, 2018

@author: seth_
'''
import os, shutil, time, tarfile, io

class BrainMaker:
    BRAIN_REQUIRED_FILES = [
        "translations.py",
        "brain.py",
        ".playground",
        ".playground/networking.ini",
        ".playground/connectors"
        ]
    
    BRAIN_PNETWORKING_TEMPLATE = """
[devices]
brainswitch = switch
brainvnic = vnic

[Config_brainvnic]
auto_enable = true
playground_address = {address}

[connections]
brainvnic = brainswitch

[routes]
__default__ = brainvnic

[Config_brainswitch]
auto_enable = true
physical_connection_type = remote
tcp_address = {switch_host}
tcp_port = {switch_port}
"""

    @classmethod
    def UnpackBrainZip(cls, brainpath, brainZip):
        file_obj = io.BytesIO(brainZip)
        tar = tarfile.open(fileobj = file_obj)
        for member in tar.getmembers():
            truePath = os.path.realpath(os.path.join(brainpath, member.name))
            if not truePath.startswith(brainpath):
                # TODO: needs to be logged.
                return False, "SecurityException: {} is an invalid path!".format(member.name)
        tar.extractall(path=brainpath)
    
    # TODO: could switch and port be different for each bot? If so, how to configure?
    def __init__(self, brainsRoot, brainSwitch, brainSwitchPort):
        self._brainsRoot = brainsRoot
        self._brainSwitch = brainSwitch
        self._brainSwitchPort = brainSwitchPort
        
    def initializeBrain(self, name, address, brainZip):
        #brainCode = self._getBrain(brainType, **kargs)
        #print("got brainCode")
        brainPath = os.path.join(self._brainsRoot, name+"."+str(time.time()))
        if os.path.exists(brainPath):
            raise Exception("Brain Path already exists")
        os.mkdir(brainPath)
        
        ppath = os.path.join(brainPath, ".playground")
        os.mkdir(ppath)
        
        networkKargs = {"address":address, "switch_host":self._brainSwitch,
                        "switch_port":self._brainSwitchPort}
        with open(os.path.join(ppath, "networking.ini"), "w+") as f:
            f.write(self.BRAIN_PNETWORKING_TEMPLATE.format(**networkKargs))
        os.mkdir(os.path.join(ppath, "connectors"))
        
        self.UnpackBrainZip(brainPath, brainZip)
        
        for requiredFile in self.BRAIN_REQUIRED_FILES:
            requiredFQFile = os.path.join(brainPath, requiredFile)
            if not os.path.exists(requiredFQFile):
                raise Exception("Invalid installation. File {} not present.".format(requiredFile))
            
        return brainPath