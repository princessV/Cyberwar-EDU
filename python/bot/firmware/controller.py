'''
Created on Feb 17, 2017

@author: sethjn
'''


import os, sys, logging, threading

from ..common.util import ReloadableImportManager, ExitReactorWithStatus

from playground_interface import BotChaperoneConnection, BotServerEndpoint
from ReprogrammingProtocol import ReprogrammingProtocol
from gameloop_interface import GameLoopCtx

from playground.network.common.PlaygroundAddress import PlaygroundAddress

from twisted.internet import reactor, threads
from twisted.internet.protocol import Factory

from playground import playgroundlog
from playground.twisted.error.ErrorHandlers import TwistedShutdownErrorHandler
from playground.crypto import CertFactory as CertFactoryRegistrar
from playground.network.message import MessageRegistry
import traceback
import time

# Allow duplicate messages to overwrite, because of reprogramming
MessageRegistry.REPLACE_DUPLICATES = True

logger = logging.getLogger(__name__)

importer = ReloadableImportManager()


def StoreErrorToManager(f):
    def Outer(self, *args, **kargs):
        try:
            success, msg = f(self, *args, **kargs)
        except Exception, e:
            tb = traceback.format_exc()
            logger.error("Data Manager error: %s\n%s" % (e,tb))
            self.manager.lastException = str(e)
            return False, "Operation failed: %s" % e
        if not success:
            self.manager.lastException = msg
        return success, msg
    return Outer

class RawDataLoader(object):
    def __init__(self, manager):
        self.manager = manager
        self.postOperation = None
        
    def setPostLoadOperation(self, f):
        self.postOperation = f
        
    @StoreErrorToManager
    def load(self, reprogrammed=False):
        filename = self.manager.manifest[0]
        with open(os.path.join(ReprogrammableData.CodeDir, filename)) as f:
            self.manager.value = f.read().strip()
        if self.postOperation:
            self.postOperation(self, reprogrammed)
        return True, "Loaded Data Value"
            
    @StoreErrorToManager
    def unpack(self, data):
        filename = self.manager.manifest[0]
        with open(os.path.join(ReprogrammableData.CodeDir, filename), "wb+") as f:
            f.write(data)
        return True, "Saved New Data Value"
            
class PythonModuleLoader(object):
    def __init__(self, manager, moduleName, postOperation=None):
        self.manager = manager
        self.moduleName = moduleName
        self.postOperation = None
        self.__dirty = False
        
    def setPostLoadOperation(self, f):
        self.postOperation = f
        
    @StoreErrorToManager
    def load(self):
        logger.debug("Trying to load module %s" % self.moduleName)
        newModule = importer.forceImport(self.moduleName)
        self.manager.value = newModule
        if self.postOperation:
            self.postOperation(self, self.__dirty)
        logger.debug("Module %s loaded" % self.moduleName)
        self.__dirty = False
        return True, "Loaded Module %s" % self.moduleName
    
    @StoreErrorToManager
    def unpack(self, data):
        tarball = self.moduleName + ".tar.gz"
        tarballPath = os.path.join(ReprogrammableData.CodeDir, tarball)
        with open(tarballPath, "wb+") as f:
            f.write(data)
        returnCode = os.system("cd %s; tar -xzf %s" % (ReprogrammableData.CodeDir, tarball))
        if returnCode:
            return False, "Failed to reprogram %s. Error Code: %d" % (self.moduleName, returnCode)
        for requiredFile in self.manager.manifest:
            if not os.path.exists(os.path.join(ReprogrammableData.CodeDir, requiredFile)):
                return False, "Failed to reprogram %s because it failed to create required file %s"% (self.moduleName, requiredFile)
        self.__dirty = True
        return True, "%s updated successfully" % self.moduleName

class ReprogrammableData(object):
    
    CodeDir = "."
    
    class DataManager(object):
        def __init__(self):
            self.value = None
            self.manifest = []
            self.loader = None
            self.lastException = ""
            
        def __call__(self):
            return self.value
            
    def __init__(self):
        self.__programmableModules = {}
        
        # REPORGRAMMABLE DATA #1: ADDRESS #
        self.address = self.DataManager()
        self.address.manifest.append("address.txt")
        self.address.loader = RawDataLoader(self.address)
        self.__programmableModules["ADDRESS"] = self.address
        
        # REPROGRAMMABLE DATA #2: PASSWORD #
        self.password = self.DataManager()
        self.password.manifest.append("password.txt")
        self.password.loader = RawDataLoader(self.password)
        self.__programmableModules["rPASSWORD"] = self.password
        
        # REPROGRAMMABLE DATA #3: CERTFACTORY #
        self.certFactory = self.DataManager()
        self.certFactory.manifest.append("CertFactory.py")
        self.certFactory.loader = PythonModuleLoader(self.certFactory, "CertFactory")
        self.__programmableModules["CERT_FACTORY"] = self.certFactory
        
        # REPROGRAMMABLE DATA #4: PROTOCOLSTACK #
        self.protocolStack = self.DataManager()
        self.protocolStack.manifest.append("ProtocolStack/__init__.py")
        self.protocolStack.loader = PythonModuleLoader(self.protocolStack, "ProtocolStack",
                                                       lambda *args: self.__restartNetwork(raw=False))
        self.__programmableModules["PROTOCOL_STACK"] = self.protocolStack
        
        # REPROGRAMMABLE DATA #5: REPROGRAMPREDICATE #
        self.rPredicate = self.DataManager()
        self.rPredicate.manifest.append("RPredicate.py")
        self.rPredicate.loader = PythonModuleLoader(self.rPredicate, "RPredicate")
        self.__programmableModules["rPREDICATE"] = self.rPredicate 

        # REPROGRAMMABLE DATA #6: BRAIN #
        self.brain = self.DataManager()
        self.brain.manifest.append("Brain/__init__.py")
        self.brain.loader = PythonModuleLoader(self.brain, "Brain")
        self.__programmableModules["BRAIN"] = self.brain
        
        self.__exceptions = {}
        
    def getModuleByName(self, name):
        return self.__programmableModules.get(name, None)
        
    def loadAllModules(self):
        print "load modules"
        for module in self.__programmableModules.values():
            print "loading module", module.loader
            module.loader.load()
    
    def popLastException(self, module):
        lastException = module.lastException
        module.lastException = ""
        return lastException



class Controller(Factory):
    protocol = ReprogrammingProtocol
    
    RAW_PORT = 666
    ADV_PORT = 667

    def __init__(self):
        
        self.__botData = ReprogrammableData()
        
        # bootstrap data. Load these now. All the other operations is after we're connected to the chaperone
        self.__botData.address.loader.load()
        self.__botData.password.loader.load()
        
        # Now set postLoad operations. Almost all of these require that the Chaperone is connected
        self.__botData.address.loader.setPostLoadOperation(lambda loader, dirty: dirty and self.__restartNetwork())
        self.__botData.certFactory.loader.setPostLoadOperation(lambda *args: self.__reloadCertificates())
        self.__botData.protocolStack.loader.setPostLoadOperation(lambda *args: self.__restartNetwork(raw=False))
        self.__botData.brain.loader.setPostLoadOperation(self.__handleBrainReload)
        
        self.__brainThread = None

        self.__rawEndpoint = None
        self.__advEndpoint = None
        
        self.__currentConnection = None
        self.__connectedToChaperone = False

        
    def __errorHandler(self, *args):
        print "Controller Failed", args
        reactor.stop()
        
    def __startReprogrammingProtocol(self, chaperoneProtocol):
        logger.info("Chaperone Connected. Start up reporgramming protocol")
        self.__connectedToChaperone = True
        
        self.__restartNetwork()
        
        # Shouldn't load our modules until chaperone connected
        # Some moules may restart the network, but that's ok
        self.__botData.loadAllModules()
        
        
    def __restartNetwork(self, raw=True, advPort=True):
        if not self.__connectedToChaperone:
            logger.info("Could not start network (yet). Still waiting on Chaperone")
            return
        stack = self
        if raw:
            self.__rawEndpoint = self.__restartNetworkServer(self.__rawEndpoint, self.RAW_PORT, stack)
        if advPort and self.__botData.protocolStack():
            stack = self.__botData.protocolStack().ListenFactory.Stack(stack)
            self.__advEndpoint = self.__restartNetworkServer(self.__advEndpoint, self.ADV_PORT, stack)
        
    def __restartNetworkServer(self, endpoint, port, stack):
        if endpoint:
            # we're still connected. Shutdown
            endpoint.close()
            
        endpoint = BotServerEndpoint(port)
        endpoint.listen(stack)
        return endpoint
    
    def __reloadCertificates(self):
        CertFactoryRegistrar.setImplementation(self.__botData.certFactory())
        self.__restartNetwork(raw = False)
        
    def __handleBrainReload(self, loader, moduleIsDirty):
        if moduleIsDirty:
            self.__loadBrainFromNetwork()
        else:
            self.__loadBrain()
        
    def __loadBrainFromNetwork(self):
        if not self.__currentConnection or not self.__currentConnection.transport:
            raise Exception("Cannot load brain from network without a network connection")
        brainOriginFile = os.path.join(ReprogrammableData.CodeDir, "brain_origin.txt")
        with open(brainOriginFile, "w+") as f:
            f.write(str(self.__currentConnection.transport.getPeer().host))
        self.__loadBrain()
        
    def __loadBrain(self):
        if self.__brainThread and self.__brainThread.isAlive():
            self.__botData.brain().stop()
            self.__brainThread.join(3.0) # Give the thread three seconds to shutdown nicely
            if self.__brainThread.isAlive():
                # Thread didn't stop nicely. Shutdown the program with code 100
                # Outside Daemon prcoess should restart
                logger.debug("Couldn't stop thread nicely. Do restart")
                reactor.callLater(0.0, ExitReactorWithStatus, reactor, 100) 
        
        threadCtx = GameLoopCtx()
        brainOriginFile = os.path.join(ReprogrammableData.CodeDir, "brain_origin.txt")
        if not os.path.exists(brainOriginFile):
            logger.info("Virgin Birthed Brain. No Origin. Any calls to connect to ORIGIN will fail.")
        else:
            with open(brainOriginFile) as f:
                threadCtx.socket.ORIGIN = f.read().strip()

        self.__brainThread = threading.Thread(target = self.__botData.brain().gameloop, args=(threadCtx,))
        self.__brainThread.daemon=True
        logger.info("Starting brain thread")
        self.__brainThread.start()
        reactor.callLater(2.0, logger.info, "Call after starting thread?")
        
    def connectToChaperone(self, chaperoneAddr, chaperonePort):
        logger.info("Connecting to chaperone at %s::%d" % (chaperoneAddr, chaperonePort))
        
        addressString = self.__botData.address()
        if not addressString:
            addressString = "666.666.666.666"
        address = PlaygroundAddress.FromString(addressString)
        d = BotChaperoneConnection.ConnectToChaperone(reactor, chaperoneAddr, chaperonePort, address)
        
        d.addCallback(self.__startReprogrammingProtocol)
        d.addErrback(self.__errorHandler)
        
    # API FOR REPROGRAMMING PROTOCOL
    def rPassword(self):
        return self.__botData.password()
    
    def reprogram(self, subsystem, data):
        dataManager = self.__botData.getModuleByName(subsystem)
        if not dataManager:
            return False, "Unknown subsystem %s" % subsystem
        success, msg = dataManager.loader.unpack(data)
        if success:
            success, msg = dataManager.loader.load()
        return success, msg
        
    def reload(self):
        self.__restartNetwork(raw=False)
        
    def setCurrentConnection(self, conn):
        self.__currentConnection = conn
        
    def buildProtocol(self, addr):
        if not self.__currentConnection:
            self.__currentConnection = Factory.buildProtocol(self, addr)
            return self.__currentConnection
        return None
    
if __name__=="__main__":
    print "Starting Bot Controller"
    
    logging.getLogger("").setLevel("INFO")
    
    # Uncomment the next line to turn on "packet tracing"
    #logctx.doPacketTracing = True
    
    playgroundlog.Config.enableLogging()
    playgroundlog.Config.enableHandler(playgroundlog.Config.STDERR_HANDLER)
    
    args = []
    opts = {"--chaperone-addr":"127.0.0.1",
            "--chaperone-port":"9090"}
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            k,v = arg.split("=")
            opts[k]=v
        else:
            args.append(arg)
    
    chaperoneAddress, chaperonePort = opts["--chaperone-addr"], opts["--chaperone-port"]
    chaperonePort = int(chaperonePort)
    controller = Controller()
    controller.connectToChaperone(chaperoneAddress, chaperonePort)
    
    TwistedShutdownErrorHandler.HandleRootFatalErrors()
    reactor.run()

    
