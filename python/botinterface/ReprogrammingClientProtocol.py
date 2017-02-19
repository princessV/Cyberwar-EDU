'''
Created on Feb 18, 2017

@author: sethjn
'''

from ReprogrammingResponse import CURRENT_VERSION as ReprogrammingResponse
from ReprogrammingRequest import  CURRENT_VERSION as ReprogrammingRequest
from twisted.internet.protocol import Protocol
from playground.network.common.Protocol import MessageStorage
from botinterface.util import InsertChecksum
from twisted.internet.defer import Deferred
from playground.twisted.endpoints.GateEndpoint import GateClientEndpoint
from twisted.internet import reactor
from twisted.internet.endpoints import connectProtocol


class ReprogrammingClientProtocol(Protocol):
    def __init__(self):
        self.__storage = MessageStorage(ReprogrammingResponse)
        self.__requests = {}
        self.__reqId = 0
        
    def __nextId(self):
        self.__reqId += 1
        return self.__reqId
        
    def dataReceived(self, data):
        self.__storage.update(data)
        for message in self.__storage.iterateMessages():
            if not self.__requests.has_key(message.RequestId):
                continue
            d = self.__requests[message.RequestId]
            d.callback(message.Data)
        
    def reprogram(self, password, subsystem, data, *additionalSubsystems):
        if len(additionalSubsystems) % 2 != 0:
            raise Exception("Arguments to reprogram is both a subsystem and the data")
        req = ReprogrammingRequest(RequestId=self.__nextId(),
                                   Opcode   =0)
        
        subsystems = [subsystem]
        programs = [data]
        
        while additionalSubsystems:
            subsystems.append(additionalSubsystems.pop(0))
            programs.append(additionalSubsystems.pop(0))
            
        subsystems = map(ReprogrammingRequest.SUBSYSTEMS.index, subsystems)
    
        req.Subsystems = subsystems
        req.Data = programs
        
        InsertChecksum(req, password=password)
        self.__requests[req.RequestId] = Deferred()
        self.transport.write(req.__serialize__())
        return self.__requests[req.RequestId]
    
    
def handleResponse(data):
    print "Got response from server"
    for serverString in data:
        print serverString
    print "Done."
    reactor.stop()
        
def reprogram(protocol, subsystem, filename):
    print "Connected to Network. Sending reprogramming information"
    with open(filename) as f:
        data = f.read()
        print "Sending %d byte program to subsystem %s" % (len(data), subsystem)
        d = protocol.reprogram("222222", subsystem, data)
        d.addCallback(handleResponse)
        
def handleError(self, *args):
    print "Something went wrong", args
    
if __name__=="__main__":
    botAddr = raw_input("Enter Bot Address:  ")
    subsystem = raw_input("Enter Subsystem to Reprogram:  ")
    filename = raw_input("Enter compressed program file:  ")
    
    playgroundEndpoint = GateClientEndpoint.CreateFromConfig(reactor, botAddr, 666)
    reprogrammingProtocol = ReprogrammingClientProtocol()
    d = connectProtocol(playgroundEndpoint, reprogrammingProtocol)
    d.addCallback(reprogram, subsystem, filename)
    d.addErrback(handleError)
    reactor.run()