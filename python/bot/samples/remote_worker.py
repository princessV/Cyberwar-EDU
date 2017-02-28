from playground.network.common.Protocol import MessageStorage
from playground.network.message.ProtoBuilder import MessageDefinition
from playground.network.message.StandardMessageSpecifiers import UINT1, UINT4, BOOL1, LIST, STRING
from playground.utils.ui import CLIShell, stdio
from playground.twisted.endpoints import GateServerEndpoint, GateClientEndpoint, PlaygroundNetworkSettings
import time, traceback, logging
from twisted.internet.protocol import Factory, Protocol
from twisted.internet import reactor

class CommandAndControlRequest(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.message"
    MESSAGE_VERSION = "1.0"
    
    COMMAND_NOOP = 0
    COMMAND_MOVE = 1
    COMMAND_LOOK = 2
    COMMAND_WORK = 4
    
    BODY = [("reqType", UINT1),
            ("ID", UINT4),
            ("parameters",LIST(STRING))
            ]
    
class CommandAndControlResponse(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.response"
    MESSAGE_VERSION = "1.0"
    BODY = [("reqID", UINT4),
            ("success", BOOL1),
            ("message", STRING)]

class RemoteWorkerBrain(object):
    def __init__(self):
        self.__running = True
        self.__lastError = None
    
    def stop(self):
        self.__running = False
        
    def lastError(self):
        return self.__lastError
    
    def gameloop(self, ctx):
        logger = logging.getLogger(__name__+".RemoteWorkerBrain")
        logger.info("Starting Game Loop")
        connected = False
        try:
            self.__running = True
            cAndC = ctx.socket()
            logger.info("Connect to %s:10001" % (ctx.socket.ORIGIN))
            cAndC.connect("ORIGIN_SERVER", 10001)
            tickCount = 0
            messageBuffer = MessageStorage(CommandAndControlRequest)
            while self.__running:
                if cAndC.connected():
                    if not connected:
                        connected = True
                        response = CommandAndControlResponse(reqID=0, success=True, message="Heartbeat 0")
                        cAndC.send(response.__serialize__())
                    if cAndC.ready():
                        data = cAndC.recv()
                        messageBuffer.update(data)
                        for msg in messageBuffer.iterateMessages():
                            
                            if msg.reqType == CommandAndControlRequest.COMMAND_NOOP:
                                response = CommandAndControlResponse(reqID = msg.ID, success=True, message="Heartbeat")
                                
                            elif msg.reqType == CommandAndControlRequest.COMMAND_MOVE:
                                direction = msg.parameters[0]
                                result, resultMessage = ctx.api.move(direction)  # convert to int if necessary
                                response = CommandAndControlResponse(reqID = msg.ID, success=result, message=resultMessage)
                                
                            elif msg.reqType == CommandAndControlRequest.COMMAND_LOOK:
                                # do look, get data, send back
                                result, resultMessage = ctx.api.look()
                                response = CommandAndControlResponse(reqID = msg.ID, success=result, message=resultMessage)
                                
                            elif msg.reqType == CommandAndControlRequest.COMMAND_WORK:
                                # do work send back result
                                pass
                            
                            else:
                                response = CommandAndControlResponse(reqID = msg.ID, success=False, message="Unknown request %d" % msg.reqType)
                            cAndC.send(response.__serialize__())
                elif tickCount > 10:
                    raise Exception("Could not connect to C&C within 10 ticks")
                tickCount += 1
                time.sleep(10)
        except Exception, e:
            errorString = traceback.format_exc()
            logger.error("Game Loop Failed: %s" % errorString)
            self.__lastError = errorString

class SimpleCommandAndControlProtocol(Protocol):
    def __init__(self, writer):
        self.storage = MessageStorage()
        self.writer = writer
        self.reqId = 1
        
    def dataReceived(self, data):
        self.storage.update(data)
        for m in self.storage.iterateMessages():
            status = m.success and "succeeded" or "failed"
            self.writer("Got Response from Bot. Operation %s. Message: %s\n" % (status, m.message))
            
    def move(self, direction):
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_MOVE,
                                           ID=self.reqId,
                                           parameters=[str(direction)])
        self.reqId += 1
        self.transport.write(request.__serialize__())
        
    def look(self):
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_LOOK,
                                           ID=self.reqId, parameters=[])
        self.reqId += 1
        self.transport.write(request.__serialize__())
            
class SimpleCommandAndControl(CLIShell, Factory):
    def __init__(self):
        CLIShell.__init__(self, prompt="[NOT CONNECTED] >> ")
        self.__protocol = None
        
    def connectionMade(self):
        moveCommandHandler = CLIShell.CommandHandler("move","Tell the bot to move (1=North, 2=South, 3=East, 4=West)",
                                                     mode=CLIShell.CommandHandler.SINGLETON_MODE,
                                                     defaultCb=self.__sendBotMove)
        lookCommandHandler = CLIShell.CommandHandler("look", "Tell the Bot to scan", self.__sendBotLook)
        
        self.registerCommand(moveCommandHandler)
        self.registerCommand(lookCommandHandler)
        
        networkSettings = PlaygroundNetworkSettings()
        networkSettings.configureNetworkStackFromPath("./ProtocolStack")
        print "Got network stack", networkSettings.networkStack
        playgroundEndpoint = GateServerEndpoint(reactor, 10001, networkSettings)
        playgroundEndpoint.listen(self)
        
    def __sendBotMove(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        direction, = args
        self.__protocol.move(direction)
        
    def __sendBotLook(self, writer):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        self.__protocol.look()
        
    def buildProtocol(self, addr):
        print "buildProtocol. Somebody is connecting to us"
        if self.__protocol:
            raise Exception("Currently, this C&C only accepts a single incoming connection")
        self.__protocol = SimpleCommandAndControlProtocol(self.transport.write)
        self.transport.write("Got connection from bot\n")
        self.prompt = "[CONNECTED] >> "
        return self.__protocol
    
singleton = RemoteWorkerBrain()
gameloop = singleton.gameloop
stop = singleton.stop
lastError = singleton.lastError

if __name__=="__main__":
    stdio.StandardIO(SimpleCommandAndControl())    
    reactor.run()
            