

class CommandAndControRequest(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.message"
    VERSION = "1.0"
    
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
    VERSION = "1.0"
    BODY = [("reqID", UINT4),
            ("success", BOOL1),
            ("message", STRING)]
    
class CommandAndControlData(Protocol):
    def dataRecieved(self, data):
        self.messageStorage.update(data)
        for msg in self.messageStorage.iterateMessages():
            if msg.reqType == CommandAndControlRequest.COMMAND_NOOP:
                response = CommandandControlResponse(reqID = msg.ID, success=True, message="Heartbeat")
            elif msg.reqType == CommandAndControlRequest.COMMAND_MOVE:
                direction = msg.parameters[0]
                result, resultMessage = move(direction)  # convert to int if necessary
                response = CommandAndControlResponse(reqID = msg.ID, success=result, message=resultMessage)
            elif msg.reqType = COMMAND_LOOK:
                # do look, get data, send back
            elif msg.reqType == COMMAND_WORK:
                # do work send back result
            else:
                response = CommandAndControlResponse(reqID = msg.ID, success=False, message="Unknown request %d" % msg.reqType)
            self.transport.write(response.__serialize__())