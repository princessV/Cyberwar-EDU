'''
Created on Feb 17, 2017

@author: sethjn
'''

import random, logging
from twisted.internet.protocol import Protocol
from playground.network.common.Protocol import StackingProtocolMixin,\
    StackingTransport, StackingFactoryMixin
from playground.network.common.PlaygroundAddress import PlaygroundAddressPair
from twisted.internet.interfaces import IStreamClientEndpoint
from zope.interface.declarations import implements
from playground.network.gate.ChaperoneProtocol import ChaperoneProtocol
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet.defer import Deferred
from playground.network.gate.ChaperoneDemuxer import ChaperoneDemuxer, Port
from twisted.internet import reactor

logger = logging.getLogger(__name__)

class BotChaperoneConnection(object):
    __muxer = None
    
    @classmethod
    def ConnectToChaperone(cls, reactor, chaperoneAddr, chaperonePort, playgroundAddress):
        if cls.__muxer:
            cls.__muxer.chaperone.connectionLost("Chaperone and/or Address Change")
            if cls.__muxer.chaperone.transport:
                cls.__muxer.chaperone.transport.loseConnection()
        chaperoneEndpoint = TCP4ClientEndpoint(reactor, chaperoneAddr, chaperonePort)
        cls.__muxer = BotMuxer(playgroundAddress)
        cls.__playgroundAddress = playgroundAddress
        return connectProtocol(chaperoneEndpoint, cls.__muxer.chaperone)
        
    @classmethod
    def Chaperone(cls):
        return cls.__muxer and cls.__muxer.chaperone or None
    
    @classmethod
    def Muxer(cls):
        return cls.__muxer

class BotClientEndpoint(BotChaperoneConnection):
    implements(IStreamClientEndpoint)

    def __init__(self, playgroundServerAddr, playgroundServerPort):
        self.__playgroundServerAddr = playgroundServerAddr
        self.__playgroundServerPort = playgroundServerPort
        self.__connectedD = Deferred()
        
    def __connectionMadeCallback(self, protocol):
        # logger "protocol connected"
        print "Callback on connection made", protocol, isinstance(protocol, StackingProtocolMixin)
        if isinstance(protocol, StackingProtocolMixin) and protocol.higherProtocol():
            d = protocol.waitForHigherConnection()
            d.addCallback(self.__connectionMadeCallback)
        else:
            self.__connectedD.callback(protocol)
    
    def connect(self, factory):
        if not self.Chaperone():
            raise Exception("Not yet connected to chaperone")
        connectProtocol = factory.buildProtocol(None)
        print "BotClientEndpoint creating protocol", connectProtocol
        print connectProtocol.applicationLayer()
        self.Muxer().connect(self.__playgroundServerAddr, self.__playgroundServerPort, connectProtocol)
        
        # todo: ensure that we got a port. But otherwise, we always callback that we connected.
        reactor.callFromThread(self.__connectionMadeCallback, connectProtocol)
        return self.__connectedD
    
class BotServerEndpoint(BotChaperoneConnection):
    implements(IStreamClientEndpoint)

    def __init__(self, listeningPort):
        self.__listeningPort = listeningPort
        self.__connectedD = Deferred()
        
    def listen(self, factory):
        if not self.Chaperone():
            raise Exception("Not yet connected to chaperone")
        listenPort = self.Muxer().listen(self.__listeningPort, factory)
        logger.debug("Listening on port %d" % listenPort)
        
    def close(self):
        self.Muxer().clearReservation(self.__listeningPort)
        
class BotTransport(object):
    
    def __init__(self, srcAddr, srcPort, dstAddr, dstPort, muxer):
        self.__muxer = muxer
        self.__srcAddr, self.__srcPort = srcAddr, srcPort
        self.__dstAddr, self.__dstPort = dstAddr, dstPort
        
    def write(self, data):
        if not self.__muxer: return
        self.__muxer.chaperone.send(self.__srcPort, self.__dstAddr, self.__dstPort, data)
        
    def getHost(self):
        return PlaygroundAddressPair(self.__srcAddr, self.__srcPort)
    
    def getPeer(self):
        return PlaygroundAddressPair(self.__dstAddr, self.__dstPort)
    
    def loseConnection(self):
        if not self.__muxer: return
        #g_logger.info("GateTransport %s to %s lose connection" % (self.getHost(),
        #                                                          self.getPeer()))
        self.__muxer.clearReservation(self.__srcPort)
        self.__muxer = None

class BotIncomingPort(Port):
    def __init__(self, portNum, muxer, spawnFactory):
        super(BotIncomingPort, self).__init__(portNum, Port.PORT_TYPE_INCOMING)
        self.__spawnFactory = spawnFactory
        self.__muxer = muxer
        
    def spawnNewConnection(self, dstAddr, dstPort):
        protocol = self.__spawnFactory.buildProtocol(self.__muxer.chaperone.gateAddress())
        if not protocol:
            raise Exception("Cannot spawn a protocol for incoming connection %s:%d" % (dstAddr, dstPort))
        
        connectionData = self.ConnectionData()
        connectionData.protocol = protocol
        
        self._connections[(dstAddr, dstPort)] = connectionData
        protocol.makeConnection(BotTransport(self.__muxer.chaperone.gateAddress(), self.number(),
                                            dstAddr, dstPort, self.__muxer))
        
class BotOutgoingPort(Port):
    def __init__(self, portNum, dstAddr, dstPort, protocol):
        super(BotOutgoingPort, self).__init__(portNum, Port.PORT_TYPE_OUTGOING)
        
        connectionData = self.ConnectionData()
        connectionData.protocol = protocol
        
        self._connections[(dstAddr, dstPort)] = connectionData
        
class BotMuxer(ChaperoneDemuxer):
    MIN_FREE_PORT = 1024
    MAX_FREE_PORT = (2**16)-1
    
    def __init__(self, playgroundAddress):
        super(BotMuxer, self).__init__()
        self.closed = False
        # this circular dependency is a hack. No better solution at this point
        # We need the chaperone for sending (transports)
        # but the Chaperone needs the muxer for receiving.
        # Later, we should separate this functionality.
        self.chaperone = ChaperoneProtocol(playgroundAddress, self)
        
    def getFreeSrcPort(self):
        for i in range(10): # 10 tries:
            srcPort = random.randint(1025,(2**16)-1)
            if not self.portInUse(srcPort):
                return srcPort
        # couldn't get a random one after 10 turns. Brute force
        super(BotMuxer, self).getFreeSrcPort()
    
    def listen(self, listenPort, factory):
        if self.portInUse(listenPort): return 0
        portObject = BotIncomingPort(listenPort, self, factory)
        self.reservePort(listenPort, portObject)
        return listenPort
    
    def connect(self, dstAddr, dstPort, protocol):
        logger.info("connecting muxer to %s:%s (protocol %s)" % (dstAddr, dstPort, protocol))
        nextPort = self.getFreeSrcPort()

        portObject = BotOutgoingPort(nextPort, dstAddr, dstPort, protocol)
        self.reservePort(nextPort, portObject)
        reactor.callFromThread(lambda: protocol.makeConnection(BotTransport(self.chaperone.gateAddress(), nextPort, dstAddr, dstPort,  self)))
        return nextPort
    
    def handleData(self, srcAddress, srcPort, dstPort, connectionData, fullPacket):
        try:
            logger.debug("Passing %d len packet to handler %s" % (len(fullPacket), connectionData.protocol))
            connectionData.protocol.dataReceived(fullPacket)
        except Exception, e:
            logger.exception("Could not process incoming packet. Reason=%s" % e)