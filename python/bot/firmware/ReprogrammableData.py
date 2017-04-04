'''
Created on Mar 1, 2017

@author: sethjn
'''

from bot.common.util import FingerPrint
from ..common.util import ReloadableImportManager

import logging, traceback, os, tarfile

from playground.network.message import MessageRegistry
from collections import OrderedDict

logger = logging.getLogger(__name__)

importer = ReloadableImportManager()

# Allow duplicate messages to overwrite, because of reprogramming
MessageRegistry.REPLACE_DUPLICATES = True


def StoreErrorToManager(f):
    def Outer(self, *args, **kargs):
        try:
            success, msg = f(self, *args, **kargs)
        except Exception, e:
            tb = traceback.format_exc()
            logger.error("Data Manager error: %s\n%s" % (e,tb))
            self._manager.lastException = tb
            return False, "Operation failed: %s" % tb
        if not success:
            self._manager.lastException = msg
        return success, msg
    return Outer

class BaseLoader(object):
    def __init__(self, manager):
        self._dirty = False
        self._manager = manager
        self._postOperation = None
        
    def originFile(self):
        raise Exception("Must be overwritten by subclass")
        
    def setPostLoadOperation(self, f):
        print "set post load operation", f
        self._postOperation = f
        
    def loadOrigin(self):
        originFile = self.originFile()
        if not os.path.exists(originFile):
            return "<virgin origin>"
        with open(originFile) as f:
            return f.read().strip()
        
    @StoreErrorToManager
    def load(self):
        result, resultMessage = self.loadFromDisk()
        if result:
            self._manager.origin = self.loadOrigin()
            self._postOperation and self._postOperation(self, self._dirty)
            self._dirty = False
        return result, resultMessage
        
    @StoreErrorToManager
    def unpack(self, origin, data):
        result, resultMessage = self.unpackToDisk(data)
        with open(self.originFile(), "wb+") as f:
            f.write(origin)
        self._dirty = True
        return result, resultMessage

class RawDataLoader(BaseLoader):
    def __init__(self, manager):
        BaseLoader.__init__(self, manager)
        
    def originFile(self):
        return os.path.join(ReprogrammableData.CodeDir, self._manager.manifest[0])+".origin"
        
    def loadFromDisk(self):
        filename = self._manager.manifest[0]
        with open(os.path.join(ReprogrammableData.CodeDir, filename)) as f:
            rawData = f.read()
            self._manager.fingerPrint = FingerPrint(rawData)
            self._manager.value = rawData.strip()
        return True, "Loaded Data Value"
            
    def unpackToDisk(self, data):
        filename = self._manager.manifest[0]
        with open(os.path.join(ReprogrammableData.CodeDir, filename), "wb+") as f:
            f.write(data)
        return True, "Saved New Data Value"
            
class PythonModuleLoader(BaseLoader):
    def __init__(self, manager, moduleName, postOperation=None):
        BaseLoader.__init__(self, manager)
        self.setPostLoadOperation(postOperation)
        self.moduleName = moduleName

    def tarballName(self):
        return self.moduleName + ".tar.gz"
    
    def tarballPath(self):
        return os.path.join(ReprogrammableData.CodeDir, self.tarballName())
    
    def originFile(self):
        return self.tarballPath()+".origin"

        
    def loadFromDisk(self):
        logger.debug("Trying to load module %s" % self.moduleName)
        newModule = importer.forceImport(self.moduleName)
        self._manager.value = newModule

        logger.debug("Module %s loaded" % self.moduleName)
        tarballPath = self.tarballPath()
        if not os.path.exists(tarballPath):
            logger.debug("Tarball module appears lost")
            self._manager.fingerPrint = "<<Source Package Missing>>"
        else:
            with open(tarballPath) as f:
                data= f.read()
                self._manager.fingerPrint = FingerPrint(data)
        return True, "Loaded Module %s" % self.moduleName
    
    def unpackToDisk(self, data):
        tarballPath = self.tarballPath()
        with open(tarballPath, "wb+") as f:
            f.write(data)
        try:
            with tarfile.open(tarballPath, "r:gz") as tf:
                tf.extractall(ReprogrammableData.CodeDir)
        except Exception, e:
            return False, "Failed to reprogram %s because %s." % (self.moduleName, str(e))
        #returnCode = os.system("cd %s; tar -xzf %s" % (ReprogrammableData.CodeDir, tarballPath))
        #if returnCode:
        #    return False, "Failed to reprogram %s. Error Code: %d" % (self.moduleName, returnCode)
        for requiredFile in self._manager.manifest:
            if not os.path.exists(os.path.join(ReprogrammableData.CodeDir, requiredFile)):
                return False, "Failed to reprogram %s because it failed to create required file %s"% (self.moduleName, requiredFile)

        return True, "%s updated successfully" % self.moduleName
    
class ReprogrammableData(object):
    
    CodeDir = "."
    
    class DataManager(object):
        def __init__(self):
            self.value = None
            self.manifest = []
            self.loader = None
            self.status = lambda: self.lastException and "Error, %" % self.lastException or "<<OK>>"
            self.lastException = ""
            self.fingerPrint = ""
            self.origin = "<virgin birth data>"
            
        def __call__(self):
            return self.value
            
    def __init__(self):
        self.__programmableModules = OrderedDict()
        self.__exceptions = {}
        
    def createModule(self, name):
        self.__programmableModules[name] = self.DataManager()
        return self.__programmableModules[name]
        
    def getModuleByName(self, name):
        return self.__programmableModules.get(name, None)
        
    def loadAllModules(self):
        logger.info("loading programmable modules")
        for module, manager in self.__programmableModules.items():
            logger.info("loading module %s" % module)
            manager.loader.load()
    
    def popLastException(self, module):
        lastException = module.lastException
        module.lastException = ""
        return lastException
