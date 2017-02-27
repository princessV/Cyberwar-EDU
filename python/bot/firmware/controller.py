'''
Created on Feb 17, 2017

@author: sethjn
'''

from playground.network.gate.ChaperoneProtocol import ChaperoneProtocol
from playground.network.common.PlaygroundAddress import PlaygroundAddress,\
    PlaygroundAddressPair
import random, os, commands, imp, sys, logging
from threading import RLock
from twisted.internet import reactor, threads
from twisted.internet.protocol import Protocol, connectionDone, Factory
from playground.network.common.Protocol import StackingProtocolMixin,\
    StackingTransport
from twisted.internet.endpoints import connectProtocol
from botinterface.playground_interface import BotClientEndpoint,\
    BotChaperoneConnection, BotServerEndpoint
from botinterface.ReprogrammingProtocol import ReprogrammingProtocol
from playground import playgroundlog
from playground.twisted.error.ErrorHandlers import TwistedShutdownErrorHandler
from playground.crypto import CertFactory as CertFactoryRegistrar
from playground.network.message import MessageRegistry

# Allow duplicate messages to overwrite, because of reprogramming
MessageRegistry.REPLACE_DUPLICATES = True

logger = logging.getLogger(__name__)

class BotPOD(object):
    def __init__(self):
        self.certFactory = None
        self.protocolStackModule = None
        self.address = "" #PlaygroundAddress(20171, random.randint(0,2**16), random.randint(0,2**16), random.randint(0,2**16))
        self.rPassword = "" #222222"#str(random.randint(0,999999))
        self.rPredicate = lambda srcAddr, message: True
        self.brain = None
        
class PlaygroundSocketProtocol(Protocol):
    def __init__(self, addr, port):
        self.__playgroundAddress = addr
        self.__playgroundPort = port
        self.__messages = []
        self.__connected = False
        self.__lock = RLock()
        
    def dataReceived(self, data):
        with self.__lock:
            self.messages.append(data)
        
    def connectionMade(self):
        with self.__lock:
            self.__connected = True
        self.__stateChangeListener.connectionMade(self.transport)
        
    def close(self):
        reactor.callFromThread(self.transport.loseConnection)
        
    def connectionLost(self, reason=connectionDone):
        with self.__lock:
            self.__connected = False
        self.__stateChangeListener.connectionLost(reason)
        
    def write(self, data):
        reactor.callFromThread(self.transport.write, data)
    
    def ready(self):
        with self.__lock:
            if self.__messages: return True
            return False
        
    def nextMessage(self):
        with self.__lock:
            if self.__messages: return self.__messages.pop(0)
            return None
        
    def connected(self):
        with self.__lock:
            return self.__connected

    
class PlaygroundSocketProtocolFactory(Factory):
    protocol = PlaygroundSocketProtocol
        
class PlaygroundOutboundSocket(object):
    
    PROTOCOL_STACK = None
    
    def __init__(self):
        self.__protocol = None
        self.__key = random.randint(2**64)
        
    def __connectCallback(self, protocol):
        self.__protocol = protocol
    
    def connect(self, addr, port):
        endpoint = BotClientEndpoint(addr, port)
        if self.PROTOCOL_STACK:
            stack = self.PROTOCOL_STACK.Stack(PlaygroundSocketProtocolFactory())
        else:
            stack = PlaygroundSocketProtocolFactory()
        d = endpoint.connect(stack)
        d.addCallback(self.__connectCallback)
    
    def recv(self):
        if not self.__protocol: return None
        return self.__protocol.nextMessage()
    
    def send(self, data):
        if not self.__protocol: return 0
        self.__protocol.write(data)
        return len(data)
    
    def close(self):
        if self.__protocol and self.__protocol.connected():
            self.__protocol.close() 
            self.__protocol = None
    
    def connected(self):
        if self.__protocol: return self.__protocol.connected()
        return False
    
    def ready(self):
        if self.__protocol: return self.__protocol.ready()
        return False
    
    def key(self):
        return self.__key
        
class BrainInterface(object):
    def __init__(self, controller):
        self.__running = False
        self.__stopped = True
        self.__playgroundSockets = []
        self.__lock = RLock()
        self.__controller = controller
        
    def signalStart(self):
        with self.__lock:
            self.__running = True
            
    def signalStop(self):
        with self.__lock:
            self.__stopped = True
            
            
    # Reading from self is *supposed* to be atomic.
    # Given that running and stopped are barriers, maybe locks aren't needed?
    def running(self): return self.__running
    def stopped(self): return self.__stopped

class ReloadableImportManager(object):
    def __init__(self):
        self.__imports = {}
        
    def forceImport(self, name):
        if self.__imports.has_key(name):
            for dependentModule in self.__imports[name]:
                del sys.modules[dependentModule]
        dependentModules = []
        currentLoad = sys.modules.keys()
        fp, pathname, desc = imp.find_module(name)
        newModule = imp.load_module(name, fp, pathname, desc)
        for module in sys.modules.keys():
            if module not in currentLoad:
                dependentModules.append(module)
        self.__imports[name] = dependentModules
        return newModule
importer = ReloadableImportManager()

class Controller(Factory):
    protocol = ReprogrammingProtocol
    
    RAW_PORT = 666
    ADV_PORT = 667
    
    def __init__(self):
        # TODO: make codeDir based on config or something
        self.__codeDir = os.path.abspath("./bot_programming")
        self.__passwordFile = os.path.abspath("password.txt")
        self.__addressFile = os.path.abspath("address.txt")
        
        self.__botData = BotPOD()
        if os.path.exists(self.__passwordFile):
            with open(self.__passwordFile) as f:
                self.__botData.rPassword = f.read().strip()
        if os.path.exists(self.__addressFile):
            with open(self.__addressFile) as f:
                self.__botData.address = f.read().strip()
        else:
            self.__botData.address="20171.666.666.666"
        self.__botData.address = PlaygroundAddress.FromString(self.__botData.address)
        print self.__botData.address

        self.__rawEndpoint = None
        self.__advEndpoint = None
        
    def __errorHandler(self, *args):
        print "Controller Failed", args
        reactor.stop()
        
    def __startReprogrammingProtocol(self, chaperoneProtocol, raw=False):
        logger.info("Chaperone Connected. Start up reporgramming protocol (raw=%s)" % raw)
        stack = self
        # We're still connected. Try to shutdown.
        curEndpoint = raw and self.__rawEndpoint or self.__advEndpoint
        if curEndpoint:
            curEndpoint.close()
        
        # OK. Not connected. Restart.
        if raw:
            endpoint = BotServerEndpoint(self.RAW_PORT)
        else:
            endpoint = BotServerEndpoint(self.ADV_PORT)
            if self.__botData.protocolStackModule:
                stack = self.__botData.protocolStackModule.ListenFactory.Stack(self)
        endpoint.listen(stack)
        if raw:
            self.__rawEndpoint = endpoint
        else:
            self.__advEndpoint = endpoint
        
    def __unpacker(self, packerName, data, requiredFiles=None):
        with open(packerName, "wb+") as f:
            f.write(data)
        returnCode = os.system("tar -xzf %s" % packerName)
        if returnCode:
            return False, "Failed to reprogram %s. Error Code: %d" % (packerName, returnCode)
        if requiredFiles:
            for requiredFile in requiredFiles:
                if not os.path.exists(requiredFile):
                    return False, "Failed to reprogram %s because it failed to create required file %s"% (packerName, requiredFile)
        return True, "%s updated successfully" % packerName
        
    def connectToChaperone(self, chaperoneAddr, chaperonePort):
        logger.info("Connecting to chaperone at %s::%d" % (chaperoneAddr, chaperonePort))
        d = BotChaperoneConnection.ConnectToChaperone(reactor, chaperoneAddr, chaperonePort, self.__botData.address)
        d.addCallback(self.__startReprogrammingProtocol, True)
        d.addErrback(self.__errorHandler)
        
    # API FOR REPROGRAMMING PROTOCOL
    def rPassword(self):
        return self.__botData.rPassword
    
    def reprogram(self, subsystem, data):
        os.chdir(self.__codeDir)
        if subsystem == "CERT_FACTORY":
            
            success, msg = self.__unpacker("CertFactory.tar.gz", data, requiredFiles=["CertFactory.py"])
            if not success:
                return success, msg
            
            try:
                newCertFactory = importer.forceImport("CertFactory")
            except Exception, e:
                return False, "Could not load new CertFactory. Error: %s" % str(e)
            self.__botData.certFactory = newCertFactory
            CertFactoryRegistrar.setImplementation(newCertFactory)
            
            return True, "Cert Factory Uploaded"
        elif subsystem == "PROTOCOL_STACK":
            success, msg = self.__unpacker("ProtocolStack.tar.gz", data, requiredFiles=["ProtocolStack/__init__.py"])
            if not success:
                return success, msg
            try:
                newStackModule = importer.forceImport("ProtocolStack")
            except Exception, e:
                return False, "Could not load ProtocolStack because %s" % str(e)
            
            self.__botData.protocolStackModule = newStackModule
            
            # OK, we've updated the rip/kiss stack. Let the brain know
            if self.__botData.brain:
                self.__botData.brain.PlaygroundSocket.PROTOCOL_STACK = newStackModule.ConnectFactory
            
            return True, "Protocol STack Updated"
        
            
            
            """return self.__unpacker("")
                  "ADDRESS",
                  "rWHITE_LIST",
                  "rPASSWORD",
                  "BRAIN"""
        else:
            return False, "Unknown subsystem %s" % subsystem
        
    def reload(self):
        #self.__startReprogrammingProtocol(None, raw=True)
        if self.__botData.protocolStackModule:
            self.__startReprogrammingProtocol(None)
    
if __name__=="__main__":
    print "Starting Bot Controller"
    
    logctx = playgroundlog.LoggingContext("bot_controller")
    logging.getLogger("").setLevel("INFO")
    
    # Uncomment the next line to turn on "packet tracing"
    #logctx.doPacketTracing = True
    
    playgroundlog.startLogging(logctx)
    playgroundlog.UseStdErrHandler(True)
    
    chaperoneAddress, chaperonePort = sys.argv[1:]
    chaperonePort = int(chaperonePort)
    controller = Controller()
    controller.connectToChaperone(chaperoneAddress, chaperonePort)
    
    TwistedShutdownErrorHandler.HandleRootFatalErrors()
    reactor.run()

    
