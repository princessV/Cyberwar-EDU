'''
Created on Feb 18, 2017

@author: sethjn
'''

import md5, imp, sys

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

class ReloadableImportManager(object):
    def __init__(self):
        self.__imports = {}
        
    def forceImport(self, name, path=None):
        if self.__imports.has_key(name):
            for dependentModule in self.__imports[name]:
                if sys.modules.has_key(dependentModule):
                    del sys.modules[dependentModule]
        dependentModules = []
        currentLoad = sys.modules.keys()
        fp, pathname, desc = imp.find_module(name, path)
        newModule = imp.load_module(name, fp, pathname, desc)
        for module in sys.modules.keys():
            if module not in currentLoad:
                dependentModules.append(module)
        self.__imports[name] = dependentModules
        return newModule

def ExitReactorWithStatus(reactor, code):
    reactor.stop()
    sys.exit(code)