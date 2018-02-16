import playground
import asyncio

from playground.common.io.ui.CLIShell import CLIShell, AdvancedStdio

import translations

Command = CLIShell.CommandHandler

class RemoteControlProtocol(asyncio.Protocol):
    def __init__(self, shell):
        self.transport = None
        self.shell = shell
        self.translator = translations.NetworkTranslator()
        self.buffer = b""
        self.waitingMessage = None

    def connection_made(self, transport):
        self.transport = transport
        self.shell.addConnection(self)

    def data_received(self, data):
        self.buffer += data
        while True:
            if self.waitingMessage is None:
                if b"\n\n" in self.buffer:
                    index = self.buffer.index(b"\n\n")
                    message = self.buffer[:index]
                    self.buffer = self.buffer[index+2:]
                    self.waitingMessage = self.translator.processHeader(message)
                else: return
            else:
                headerType, headerArg, headers = self.waitingMessage
                contentLength = int(headers.get(b"Content_length", "0"))
                if len(self.buffer) < contentLength:
                    return
                body, self.buffer = self.buffer[:contentLength], self.buffer[contentLength:]
                self.waitingMessage = None

                try:
                    cmd = self.translator.unmarshallFromNetwork(headerType, headerArg, headers, body)
                    self.shell.handleNetworkData(self, cmd)
                except Exception as e:
                    self.shell.handleNetworkException(self, e)

    def connection_lost(self, reason=None):
        self.shell.removeConnection(self)

class RemoteConsole(CLIShell):
    STD_PROMPT = "[null] >> "

    DIRECTIONS_SHORT = {
        "n":"north",
        "ne":"north-east",
        "e":"east",
        "se":"south-east",
        "s":"south",
        "sw":"south-west",
        "w":"west",
        "nw":"north-west"
    }

    def __init__(self):
        super().__init__(prompt=self.STD_PROMPT)
        self._protocolId = 0
        self._selected = None
        self._protocols = {}

        switchobjectHandler = Command("switch",
                                      "Switch object to control",
                                      self._switchObjectCommand)
        sendcommandHandler  = Command("send",
                                      "Send command to object",
                                      self._sendCommand)
        listobjectsHandler  = Command("list",
                                      "list current connections",
                                      self._listCommand)
        self.registerCommand(switchobjectHandler)
        self.registerCommand(sendcommandHandler)
        self.registerCommand(listobjectsHandler)

        coro = playground.create_server(lambda: RemoteControlProtocol(self), port=10013, family="peep")
        asyncio.ensure_future(coro)

    def addConnection(self, protocol):
        self._protocolId += 1
        self._protocols[self._protocolId] = protocol

    def removeConnection(self, protocol):
        k = None
        for k in self._protocols:
            if self._protocols[k] == protocol: break
        if k is not None:
            del self._protocols[k]

    def handleNetworkException(self, protocol, e):
        self.transport.write("Network Failure: {}\n\n".format(e))

    def createScanResultsDisplay(self, scanResults):
        mapPart = ""
        textPart = ""
        mapLine = ""
        lastY = None
        for coord, objDataList in scanResults:
            x,y = coord
            if y != lastY:
                mapPart = mapLine + "\n" + mapPart
                lastY = y
                mapLine = ""
            terrain = None
            obj = None
            for objData in objDataList:
                d = dict(objData)
                if d["type"] == "terrain":
                    terrain = d["identifier"]
                elif d["type"] == "object":
                    obj = d["identifier"] + " (" + d["attributes"] + ")"
            if obj is not None:
                mapLine += "O"
                textPart += "Object at {}: {}\n".format(coord, obj)
            elif terrain == "land":
                mapLine += "#"
            elif terrain == "water":
                mapLine += "="

        mapPart = mapLine + "\n" + mapPart + "\n"
        return mapPart + textPart + "\n"
        

    def handleNetworkData(self, protocol, data):
        if isinstance(data, translations.BrainConnectResponse):
            self.transport.write("Brain Connected. Attributes={}\n".format(data.attributes))
            protocol.translator = translations.NetworkTranslator(*data.attributes)
            self.transport.write("Attributes Loaded\n\n")
        elif isinstance(data, translations.FailureResponse):
            self.transport.write("Something's wrong!: {}\n\n ".format( data.message))
        elif isinstance(data, translations.ResultResponse):
            self.transport.write("Result: {}\n\n".format(data.message))
        elif isinstance(data, translations.ScanResponse):
            self.transport.write(self.createScanResultsDisplay(data.scanResults))
            self.transport.write("\n")
        elif isinstance(data, translations.MoveCompleteEvent):
            self.transport.write("Move result: {}\n\n".format(data.message))
        elif isinstance(data, translations.ObjectMoveEvent):
            if data.status == "insert":
                verb = "arrived at"
            else:
                verb = "left"
            self.transport.write("{} {} {}".format(data.objectIdentifier, verb, data.location)) 
        else:
            self.transport.write("Got {}\n\n".format(data))
        self.transport.refreshDisplay()

    def _listCommand(self, writer):
        objKeys = list(self._protocols.keys())
        objKeys.sort()
        for k in objKeys:
            writer("Object {} at {}\n".format(k, self._protocols[k].transport.get_extra_info("peername")))
        writer("\n")

    def _switchObjectCommand(self, writer, arg1):
        objId = int(arg1)
        if objId not in self._protocols:
            writer("No object {}\n".format(arg1))
            self.prompt = self.STD_PROMPT
        else:
            self._selected = objId
            writer("Object {} selected\n".format(arg1))
            self.prompt = "[{}] >> ".format(arg1)
        writer("\n")

    def _sendCommand(self, writer, cmd, *args):
        if self._selected is None:
            writer("No remote object selected.\n\n")
            return

        protocol = self._protocols.get(self._selected, None)
        if protocol is None:
            writer("Selected object no longer available.\n\n")
            self.prompt = self.STD_PROMPT
            return

        if cmd == "scan":
            cmdObj = translations.ScanCommand()
            sendData = protocol.translator.marshallToNetwork(cmdObj)
            protocol.transport.write(sendData)
            writer("Scan Message Sent.\n\n")
        elif cmd == "move":
            if len(args) != 1:
                writer("Require a direction argument (N, NE, E, SE, S, SW, W, NW)\n\n")
                return
            direction = args[0].lower()
            if direction in self.DIRECTIONS_SHORT:
                direction = self.DIRECTIONS_SHORT[direction]
            if direction not in self.DIRECTIONS_SHORT.values():
                writer("Unknown direction {}\n\n".format(direction))
                return
            cmdObj = translations.MoveCommand(direction)
            sendData = protocol.translator.marshallToNetwork(cmdObj)
            protocol.transport.write(sendData)
            writer("Move Message Sent.\n\n")
        else:
            writer("Unknown Command {}\n\n".format(cmd))


    def start(self):
        loop = asyncio.get_event_loop()
        self.registerExitListener(lambda reason: loop.call_later(1.0, loop.stop))
        AdvancedStdio(self)


if __name__=="__main__":
    shell = RemoteConsole()
    asyncio.get_event_loop().call_soon(shell.start)
    asyncio.get_event_loop().run_forever() 
