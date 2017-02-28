

class CommandAndControRequest(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.message"
    VERSION = "1.0"
    
    COMMAND_AUTO_WORK = 0
    COMMAND_AUTO_RETURN_HOME = 1
    COMMAND_AUTO_ATTACK = 2
    COMMAND_AUTO_FULLSTOP = 3
    COMMAND_GET_STATUS = 4
    COMMAND_CLEAR_ERROR = 5
    
    BODY = [("reqType", UINT1),
            ("ID", UINT4),
            ]
    
class CommandAndControlResponse(MessageDefinition):
    PLAYGROUND_IDENTIFIER = "my.commandandcontrol.response"
    VERSION = "1.0"
    BODY = [("reqID", UINT4),
            ("success", BOOL1),
            ("message", STRING)]
    
class WorkerBrain(object):
    def __init__(self):
        self.mode = FULLSTOP
        
    def operate(self):
        if self.mode == FULLSTOP or self.mode == ERROR:
            pass # do nothing
        elif self.mode == RETURN_HOME:
            if self.location() == self.homelocation:
                pass
            else:
                nextSquare = self.pathfinding(self.homelocation) # maybe A-star?
                self.move(nextSquareDirection)
        elif self.mode == ATTACK:
            if self.target == None:
                # look
                # if any enemies: set one as target
                # otherwise, keep looking
            nextSquare = self.pathfinding(self.target.location)
            self.move(nextSquareDirection)  # try to ram target
        elif self.mode == WORK:
            if self.inventory == full:
                # return home
                # if home, release inventory
            elif self.work_square == None:
                # look
                # find any work squares? if so, set one as work_square
                # otherwise, search? maybe need another mode (explore?)
            elif self.location() == self.nextSquare.location:
                self.work()
            else:
                nextSquare = self.pathfinding(self.work_square.location)
                self.move(nextSquareDirection)
        else:
            # etc
        self.reschedule(timer) # reschedule using twisted's reactor
                
    
class CommandAndControlData(Protocol):
    def dataRecieved(self, data):
        self.messageStorage.update(data)
        for msg in self.messageStorage.iterateMessages():
            # similar input/output as remote worker