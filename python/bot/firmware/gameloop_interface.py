'''
Created on Feb 22, 2017

@author: sethjn
'''

import random

from threading import RLock
from playground_interface import BotClientEndpoint

from twisted.internet import reactor
from twisted.internet.protocol import Protocol, connectionDone, Factory

class GameLoopCtx(object):
    def __init__(self):
        self.socket = PlaygroundOutboundSocket
        self.api = DummyAPI()
        
class DummyAPI(object):
    def move(self, direction):
        return True, "Moved %s" % direction
    
    def look(self):
        return True, "It is dark. You are likely to be eaten by a Grue"
    
    def work(self):
        return True, "On the railroad. All day."

class PlaygroundSocketProtocol(Protocol):
    def __init__(self):
        self.__messages = []
        self.__connected = False
        self.__lock = RLock()
        
    def dataReceived(self, data):
        with self.__lock:
            self.__messages.append(data)
        
    def connectionMade(self):
        print self, "connectionMade"
        with self.__lock:
            self.__connected = True
        Protocol.connectionMade(self)
        print "done with connection made"
        #self.__stateChangeListener.connectionMade(self.transport)
        
    def close(self):
        reactor.callFromThread(self.transport.loseConnection)
        
    def connectionLost(self, reason=connectionDone):
        with self.__lock:
            self.__connected = False
        #self.__stateChangeListener.connectionLost(reason)
        Protocol.connectionLost(self, reason)
        
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
        
    def checkConnected(self):
        with self.__lock:
            print "returnning connected"
            return self.__connected

    
class PlaygroundSocketProtocolFactory(Factory):
    protocol = PlaygroundSocketProtocol
        
class PlaygroundOutboundSocket(object):
    
    PROTOCOL_STACK = None
    ORIGIN = None
    
    def __init__(self):
        self.__protocol = None
        self.__key = random.randint(0, (2**64)-1)
        
    def __connectCallback(self, protocol):
        print "connect callback", protocol
        self.__protocol = protocol
    
    def connect(self, addr, port):
        if addr == "ORIGIN_SERVER":
            if self.ORIGIN: addr = self.ORIGIN
            else: raise Exception("No Origin Server Specified")
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
        if self.__protocol and self.__protocol.checkConnected():
            self.__protocol.close() 
            self.__protocol = None
    
    def connected(self):
        if self.__protocol: 
            return self.__protocol.checkConnected()
        return False
    
    def ready(self):
        if self.__protocol: return self.__protocol.ready()
        return False
    
    def key(self):
        return self.__key