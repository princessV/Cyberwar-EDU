'''
Created on Feb 18, 2017

@author: sethjn
'''

from ..common.network import ReprogrammingResponse, ReprogrammingRequest
from ..common.util import InsertChecksum

from twisted.internet.protocol import Protocol
from playground.network.common.Protocol import MessageStorage
from twisted.internet.defer import Deferred
from playground.twisted.endpoints.GateEndpoint import GateClientEndpoint
from twisted.internet import reactor
from twisted.internet.endpoints import connectProtocol

# these are playground utils
from utils.ui import CLIShell, stdio

import sys, os
try:
    import ProtocolStack
except:
    ProtocolStack = None


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
    
    
class ReprogrammingShellProtocol(CLIShell):
    PROMPT = "[NOT CONNECTED] >>"
    
    RAW_PORT = 666
    ADV_PORT = 667
    
    def __init__(self, botAddress):
        CLIShell.__init__(self, prompt=self.PROMPT)
        self.__botAddress = botAddress
        self.__connectPort = self.RAW_PORT
        self.__protocol = None
        
    def connectionMade(self):
        self.connectToBot(self.__connectPort)
        self.__loadCommands()
        
    def __botConnectionMade(self, protocol):
        self.transport.write("Connected to Bot.\n")
        self.__protocol = protocol
        self.prompt = "[%s::%d] >>" % (self.__botAddress, self.__connectPort)
        
    def __reprogram(self, writer, *args):
        if not self.__protocol:
            writer("Not yet connected. Cannot reprogram\n")
            return 
        subsystem, reprogramArgument = args
        if subsystem not in ReprogrammingRequest.SUBSYSTEMS:
            self.transport.write("Unknown subsystem %s. Options are %s." % (subsystem, ReprogrammingRequest.SUBSYSTEMS))
            return
        if subsystem in ["rPASSWORD", "ADDRESS"]:
            dataToSend = reprogramArgument
        else:
            if not os.path.exists(reprogramArgument):
                self.transport.write("File not found %s" % reprogramArgument)
                return
            
            with open(reprogramArgument) as f:
                dataToSend = f.read()
        writer("Sending %d byte program to subsystem %s\n" % (len(dataToSend), subsystem))
        d = self.__protocol.reprogram("222222", subsystem, dataToSend)
        d.addCallback(self.handleResponse)
        
    def __loadCommands(self):
        toggleCommandHandler = CLIShell.CommandHandler("toggle","Toggle between raw and advanced connection",self.__toggleConnection)
        reprogramCommandHandler = CLIShell.CommandHandler("reprogram", "Reprogram the bot's subsystems", 
                                                          mode=CLIShell.CommandHandler.SINGLETON_MODE,
                                                          defaultCb=self.__reprogram)
        
        self.registerCommand(toggleCommandHandler)
        self.registerCommand(reprogramCommandHandler)
        
    def __toggleConnection(self, writer):
        if self.__connectPort == self.RAW_PORT:
            self.connectToBot(self.ADV_PORT)
        else: self.connectToBot(self.RAW_PORT)
        
    def connectToBot(self, port):
        if self.__protocol:
            self.transport.write("Closing old bot connection on %d\n" % self.__connectPort)
            self.__protocol.transport.loseConnection()
            self.transport.write("Reloading protocol\n")
            self.__protocol = None
            self.prompt = self.PROMPT
        self.__connectPort = port
        
        stack = port == self.ADV_PORT and ProtocolStack or None
        playgroundEndpoint = GateClientEndpoint.CreateFromConfig(reactor, self.__botAddress, port, networkStack=stack)
        self.transport.write("Got Endpoint\n")
        reprogrammingProtocol = ReprogrammingClientProtocol()
        self.transport.write("Got protocol. Trying to connect\n")
        d = connectProtocol(playgroundEndpoint, reprogrammingProtocol)
        self.transport.write("Setting callback\n")
        d.addCallback(self.__botConnectionMade)
        d.addErrback(self.handleError)
        self.transport.write("Waiting for callback\n")
    
    
    def handleResponse(self, data):
        self.transport.write("Received response from server.\n")
        for serverString in data:
            self.transport.write("\t%s\n" % serverString)
            
    def handleError(self, *args):
        self.transport.write("Something went wrong\n", args)
    
if __name__=="__main__":
    address = sys.argv[1]
    stdio.StandardIO(ReprogrammingShellProtocol(address))    
    reactor.run()