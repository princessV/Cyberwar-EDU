'''
Created on Feb 17, 2017

@author: sethjn
'''


import os, sys, logging, threading

from ..common.util import ExitReactorWithStatus

from ReprogrammableData import ReprogrammableData, RawDataLoader, PythonModuleLoader

from playground_interface import BotChaperoneConnection, BotServerEndpoint
from ReprogrammingProtocol import ReprogrammingProtocol
from gameloop_interface import GameLoopCtx

from playground.network.common.PlaygroundAddress import PlaygroundAddress

from twisted.internet import reactor, threads
from twisted.internet.protocol import Factory

from playground import playgroundlog
from playground.twisted.error.ErrorHandlers import TwistedShutdownErrorHandler
from playground.crypto import CertFactory as CertFactoryRegistrar

import traceback
import time
from bot.firmware.gameloop_interface import PlaygroundOutboundSocket

logger = logging.getLogger(__name__)


class Controller(Factory):
    protocol = ReprogrammingProtocol
    
    RAW_PORT = 666
    ADV_PORT = 667

    def __init__(self):
        
        self.__botData = ReprogrammableData()
        self.__defineReloadableModules()
        
        # bootstrap data. Load these now. All the other operations is after we're connected to the chaperone
        self.__botData.address.loader.load()
        self.__botData.password.loader.load()
        
        self.__brainThread = None

        self.__rawEndpoint = None
        self.__advEndpoint = None
        
        self.__connectedToChaperone = False
        
    def __defineReloadableModules(self):
        # REPORGRAMMABLE DATA #1: ADDRESS #
        self.__botData.address = self.__botData.createModule("ADDRESS")
        self.__botData.address.manifest.append("address.txt")
        self.__botData.address.loader = RawDataLoader(self.__botData.address)
        
        # if the address is *reprogrammed* (dirty = True), reconnect to chaperone
        self.__botData.address.loader.setPostLoadOperation(lambda loader, dirty: dirty and self.reconnectToChaperone())
        
        # REPROGRAMMABLE DATA #2: PASSWORD #
        self.__botData.password = self.__botData.createModule("PASSWORD")
        self.__botData.password.manifest.append("password.txt")
        self.__botData.password.loader = RawDataLoader(self.__botData.password)
        
        # REPROGRAMMABLE DATA #3: CERTFACTORY #
        self.__botData.certFactory = self.__botData.createModule("CERT_FACTORY")
        self.__botData.certFactory.manifest.append("CertFactory.py")
        self.__botData.certFactory.loader = PythonModuleLoader(self.__botData.certFactory, "CertFactory")
        self.__botData.certFactory.loader.setPostLoadOperation(lambda *args: self.__reloadCertificates())
        
        # REPROGRAMMABLE DATA #4: PROTOCOLSTACK #
        self.__botData.protocolStack = self.__botData.createModule("PROTOCOL_STACK")
        self.__botData.protocolStack.manifest.append("ProtocolStack/__init__.py")
        self.__botData.protocolStack.loader = PythonModuleLoader(self.__botData.protocolStack, "ProtocolStack")
        
        # If the protocol stack changes, restart the 667 listener with the new stack
        self.__botData.protocolStack.loader.setPostLoadOperation(lambda *args: self.__restartNetwork(raw=False))
        
        # REPROGRAMMABLE DATA #5: REPROGRAMPREDICATE #
        self.__botData.predicate = self.__botData.createModule("PREDICATE")
        self.__botData.predicate.manifest.append("Predicate.py")
        self.__botData.predicate.loader = PythonModuleLoader(self.__botData.predicate, "Predicate")

        # REPROGRAMMABLE DATA #6: BRAIN #
        self.__botData.brain = self.__botData.createModule("BRAIN")
        self.__botData.brain.manifest.append("Brain/__init__.py")
        self.__botData.brain.loader = PythonModuleLoader(self.__botData.brain, "Brain")
        self.__botData.brain.loader.setPostLoadOperation(self.__handleBrainReload)
        self.__botData.brain.status = self.__getBrainStatus

        
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
        logger.info("Restart network %s %s" % (raw and "Raw" or "", advPort and "Protocol" or ""))
        if not self.__connectedToChaperone:
            logger.info("Could not start network (yet). Still waiting on Chaperone")
            return
        stack = self
        if raw:
            self.__rawEndpoint = self.__restartNetworkServer(self.__rawEndpoint, self.RAW_PORT, stack)
        if advPort and self.__botData.protocolStack():
            try:
                stack = self.__botData.protocolStack().ListenFactory.Stack(stack)
                self.__advEndpoint = self.__restartNetworkServer(self.__advEndpoint, self.ADV_PORT, stack)
            except Exception, e:
                self.__botData.protocolStack.lastException = e
                
        if self.__botData.protocolStack():
            botData = self.__botData
            print "Setting playground stack to use", botData.protocolStack().ConnectFactory
            # python appears to be weird about assigning a lambda as a class variable. Turns it into an unbound method. So self is required
            PlaygroundOutboundSocket.PROTOCOL_STACK = lambda self, *args, **kargs: botData.protocolStack().ConnectFactory.Stack(*args, **kargs)
        else:
            PlaygroundOutboundSocket.PROTOCOL_STACK = None
        
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
        self.__loadBrain()
            
    def __getBrainStatus(self):
        if self.__botData.brain():
            return "\nBrain running: %s\nLast exception: %s" % (self.__brainThread and self.__brainThread.isAlive()  or False, 
                                                              self.__botData.brain.lastException)
        else:
            return "Brain Not Loaded"

        
    def __runGameLoop(self, *args, **kargs):
        try:
            self.__botData.brain().gameloop(*args, **kargs)
        except Exception, e:
            errorMsg = traceback.format_exc()
            logger.error("Game loop failed. Reason=%s" % errorMsg)
            self.__botData.brain.lastException = errorMsg
        
    def __loadBrain(self):
        if self.__brainThread and self.__brainThread.isAlive():
            self.__botData.brain().stop()
            self.__brainThread.join(5.0) # Give the thread three seconds to shutdown nicely
            if self.__brainThread.isAlive():
                # Thread didn't stop nicely. Shutdown the program with code 100
                # Outside Daemon prcoess should restart
                logger.debug("Couldn't stop thread nicely. Do restart")
                reactor.callLater(0.0, ExitReactorWithStatus, reactor, 100) 
        
        threadCtx = GameLoopCtx()
        threadCtx.socket.ORIGIN = self.__botData.brain.origin

        self.__brainThread = threading.Thread(target = self.__runGameLoop, args=(threadCtx,))
        self.__brainThread.daemon=True
        logger.info("Starting brain thread")
        self.__brainThread.start()
        reactor.callLater(2.0, logger.info, "Call after starting thread?")
        
    def connectToChaperone(self, details):
        self.__chaperoneDetails = details
        self.reconnectToChaperone()
        
    def reconnectToChaperone(self):
        logger.info("Bot Connecting to Chaperone at %s" % self.__chaperoneDetails)
        
        addressString = self.__botData.address()
        if not addressString:
            addressString = "666.666.666.666"
        address = PlaygroundAddress.FromString(addressString)
        d = BotChaperoneConnection.ConnectToChaperone(reactor,
                                                      self.__chaperoneDetails,
                                                      address)
        
        d.addCallback(self.__startReprogrammingProtocol)
        d.addErrback(self.__errorHandler)
        
    # API FOR REPROGRAMMING PROTOCOL
    def password(self):
        return self.__botData.password()
    
    def reprogram(self, protocol, subsystem, data):
        dataManager = self.__botData.getModuleByName(subsystem)
        if not dataManager:
            return False, "Unknown subsystem %s" % subsystem
        success, msg = dataManager.loader.unpack(str(protocol.transport.getPeer().host), data)
        if success:
            success, msg = dataManager.loader.load()
        return success, dataManager.fingerPrint, msg
    
    def subsystemStatus(self, subsystem):
        dataManager = self.__botData.getModuleByName(subsystem)
        if not dataManager:
            return False, None, "Unknown subsystem %s" % subsystem
        status = dataManager.status()
        return True, dataManager.fingerPrint, "Subsystem %s status: %s" % (subsystem, status)
        
    def reload(self):
        pass # self.__restartNetwork(raw=False)
        


def run(details):
    controller = Controller()
    controller.connectToChaperone(details)
    TwistedShutdownErrorHandler.HandleRootFatalErrors()
    reactor.run()


if __name__=="__main__":
    import argparse
    
    originalCommand = "python -m bot.firmware.controller "+" ".join(sys.argv[1:])
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--chaperone-addr", default="127.0.0.1")
    parser.add_argument("--chaperone-port", default="9090")
    parser.add_argument("--chaperone-sock", default=None)
    parser.add_argument("--daemon", action="store_true", default=False)
    playgroundlog.ConfigureArgParser(parser, default="DEBUG", rootLogging=True)
    
    opts = parser.parse_args()
    if opts.daemon:
        processCommand = originalCommand.replace("--daemon","")
        deathCount = 0
        while deathCount < 10:
            starttime = time.time()
            os.system("%s" % processCommand)
            deathCount += 1
            endtime = time.time()
            runtime = endtime - starttime
            deathCount = max(0, deathCount - int(runtime/60))
        print "Too many deaths of the controller. Exit for real"
        sys.exit(-1)
    
    print "Starting Bot Controller"

    if opts.chaperone_sock is not None:
        run((opts.chaperone_addr, int(opts.chaperone_port)))
    else:
        run((opts.chaperone_sock,))
