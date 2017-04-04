from playground.network.common.Protocol import MessageStorage
from playground.network.message.ProtoBuilder import MessageDefinition
from playground.network.message.StandardMessageSpecifiers import UINT1, UINT4, BOOL1, LIST, STRING
from playground.utils.ui import CLIShell, stdio
from playground.twisted.endpoints import GateServerEndpoint, GateClientEndpoint, PlaygroundNetworkSettings
import time, traceback, logging
from twisted.internet.protocol import Factory, Protocol
from twisted.internet import reactor
from twisted.internet.defer import Deferred

class CommandAndControlRequest(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.message"
    MESSAGE_VERSION = "1.0"
    
    COMMAND_NOOP = 0
    COMMAND_MOVE = 1
    COMMAND_LOOK = 2
    COMMAND_WORK = 4
    COMMAND_UNLOAD = 5
    COMMAND_INVENTORY = 6
    COMMAND_LOCATION = 7
    
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
    
    def processRequest(self, ctx, msg):
        if msg.reqType == CommandAndControlRequest.COMMAND_NOOP:
            result = True
            resultMessage = "Heartbeat"
            
        elif msg.reqType == CommandAndControlRequest.COMMAND_MOVE:
            direction = msg.parameters[0]
            if len(msg.parameters) > 1:
                count = int(msg.parameters[1])
                if count < 1:
                    raise Exception("Cannot move less than 1 times")
            else: count = 1
            
            # use blocking to make sure each move completes before the next one
            #if count > 1: ctx.api.setBlocking(True)
            for i in range(count-1):
                result, resultMessage = ctx.api.move(direction)  # convert to int if necessary
                yield result, resultMessage
            # this result, resultMessage pair is yielded at the end of the function
            #result, resultMessage = 
            if direction.lower()[0] == "n":
                ctx.api.move_north(count)
            elif direction.lower()[0] == "s":
                ctx.api.move_south(count)
            elif direction.lower()[0] == "e":
                ctx.api.move_east(count)
            elif direction.lower()[0] == "w":
                ctx.api.move_west(count)
            result, resultMessage = True, "Moved"
            #ctx.api.setBlocking(False)
            
        elif msg.reqType == CommandAndControlRequest.COMMAND_LOOK:
            # do look, get data, send back
            #result, resultMessage = 
            result = ctx.api.look()
            result, resultMessage = True, "\n".join("%s %d %d %d %d" % (r.type, r.position.x, r.position.y, r.position.width, r.position.height) for r in result)
            
        elif msg.reqType == CommandAndControlRequest.COMMAND_WORK:
            #result, resultMessage = 
            try:
                ctx.api.work()
                result, resultMessage = True, "Worked."
            except Exception, e:
                result, resultMessage = False, str(e)
        
        elif msg.reqType == CommandAndControlRequest.COMMAND_UNLOAD:
            result, resultMessage = ctx.api.unload()
            
        elif msg.reqType == CommandAndControlRequest.COMMAND_INVENTORY:
            #result, resultMessage = ctx.api.inventory()
            inventory = ctx.api.inventory()
            invStr = ""
            for k,v in inventory:
                try:
                    invStr += "%s (%d)\n" % (k, v)
                except:
                    invStr += "unknown %s (%d)\n" % (k.__class__, v)
            result, resultMessage = True, invStr
            
        elif msg.reqType == CommandAndControlRequest.COMMAND_LOCATION:
            position= ctx.api.position
            result, resultMessage = True, "(%d, %d)" % (position.x, position.y)
        
        else:
            result = False
            resultMessage = "Unknown request %d" % msg.reqType
        yield result, resultMessage
    
    def gameloop(self, ctx):
        logger = logging.getLogger(__name__+".RemoteWorkerBrain")
        logger.info("Starting Game Loop")

        self.__running = True
        cAndC = ctx.socket()
        logger.info("Connect to %s:10001" % (ctx.socket.ORIGIN))
        cAndC.connect("ORIGIN_SERVER", 10001)
        tickCount = 0
        connected = False
        messageBuffer = MessageStorage(CommandAndControlRequest)
        while self.__running:
            tickCount += 1
            if cAndC.connected():
                if not connected:
                    connected = True
                    tickCount = 0
                if tickCount % 60 == 0:
                    logger.info("Sending heartbeat at tickcount %d" % tickCount)
                    response = CommandAndControlResponse(reqID=0, success=True, message="Heartbeat %d" % tickCount)
                    cAndC.send(response.__serialize__())
                    
                data = cAndC.recv(timeout=1)
                if not data: 
                    continue
                
                messageBuffer.update(data)
                for msg in messageBuffer.iterateMessages():
                    try:
                        for result, resultMessage in self.processRequest(ctx, msg):
                            response = CommandAndControlResponse(reqID = msg.ID, success=result, message=resultMessage)
                            cAndC.send(response.__serialize__())
                    except Exception, e:
                        response = CommandAndControlResponse(reqID = msg.ID, success=False, message="Error: %s" % e)
                        cAndC.send(response.__serialize__())
            elif tickCount % 10 == 9:
                logger.info("Could not connect to C&C within %d ticks" % (tickCount+1))
            if not cAndC.connected(): time.sleep(1)

class SimpleCommandAndControlProtocol(Protocol):
    def __init__(self):
        self.storage = MessageStorage(CommandAndControlResponse)
        
    def dataReceived(self, data):
        self.storage.update(data)
        for m in self.storage.iterateMessages():
            self.factory.handleResponse(m)
            
class SimpleCommandAndControl(CLIShell, Factory):
    def __init__(self):
        CLIShell.__init__(self, prompt="[NOT CONNECTED] >> ")
        self.__protocol = None
        self.__reqId = 1
        
    def __nextId(self):
        nextId = self.__reqId
        self.__reqId += 1
        return nextId
        
    def connectionMade(self):
        moveCommandHandler = CLIShell.CommandHandler("move","Tell the bot to move (1=North, 2=South, 3=East, 4=West)",
                                                     mode=CLIShell.CommandHandler.SINGLETON_MODE,
                                                     defaultCb=self.__sendBotMove)
        lookCommandHandler = CLIShell.CommandHandler("look", "Tell the Bot to scan", self.__sendBotLook)
        workCommandHandler = CLIShell.CommandHandler("work", "Tell the Bot to work", self.__sendBotWork)
        inventoryCommandHandler = CLIShell.CommandHandler("inventory", "Get the bot's inventory", self.__sendBotInventory)
        unloadCommandHandler = CLIShell.CommandHandler("unload", "Tell the Bot to unload inventory", self.__sendBotUnload)
        locationCommandHandler = CLIShell.CommandHandler("location", "Get the bot's location", self.__sendBotLocation)
        
        self.registerCommand(moveCommandHandler)
        self.registerCommand(lookCommandHandler)
        self.registerCommand(workCommandHandler)
        self.registerCommand(unloadCommandHandler)
        self.registerCommand(locationCommandHandler)
        self.registerCommand(inventoryCommandHandler)
        
        networkSettings = PlaygroundNetworkSettings()
        networkSettings.configureNetworkStackFromPath("./ProtocolStack")
        playgroundEndpoint = GateServerEndpoint(reactor, 10001, networkSettings)
        playgroundEndpoint.listen(self)
        
        self.deferToResponse = Deferred()
        
    def handleResponse(self, resp):
        status = resp.success and "succeeded" or "failed"
        self.transport.write("Got Response from Bot. Operation %s. Message: %s\n" % (status, resp.message))
        self.refreshInterface()
        
    def __sendBotMove(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        direction = args[0]
        if len(args) > 1:
            count = args[1]
        else:
            count = "1"
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_MOVE,
                                           ID=self.__nextId(),
                                           parameters=[str(direction), count])
        self.__protocol.transport.write(request.__serialize__())
        
    def __sendBotLook(self, writer):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_LOOK,
                                           ID=self.__nextId(), parameters=[])
        self.__protocol.transport.write(request.__serialize__())
        
    def __sendBotWork(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_WORK,
                                           ID=self.__nextId(), parameters=[])
        self.__protocol.transport.write(request.__serialize__())
        
    def __sendBotInventory(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_INVENTORY,
                                           ID=self.__nextId(), parameters=[])
        self.__protocol.transport.write(request.__serialize__())
        
    def __sendBotUnload(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_UNLOAD,
                                           ID=self.__nextId(), parameters=[])
        self.__protocol.transport.write(request.__serialize__())
        
    def __sendBotLocation(self, writer, *args):
        if not self.__protocol:
            writer("No bot connected\n")
            return
        request = CommandAndControlRequest(reqType=CommandAndControlRequest.COMMAND_LOCATION,
                                           ID=self.__nextId(), parameters=[])
        self.__protocol.transport.write(request.__serialize__())
        
        
    def buildProtocol(self, addr):
        print "buildProtocol. Somebody is connecting to us"
        if self.__protocol:
            raise Exception("Currently, this C&C only accepts a single incoming connection")
        self.__protocol = SimpleCommandAndControlProtocol()
        self.__protocol.factory = self
        self.transport.write("Got connection from bot\n")
        self.prompt = "[CONNECTED] >> "
        return self.__protocol
    
singleton = RemoteWorkerBrain()
gameloop = singleton.gameloop
stop = singleton.stop

if __name__=="__main__":
    stdio.StandardIO(SimpleCommandAndControl())    
    reactor.run()
            
