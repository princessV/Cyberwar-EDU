
class GameMessage:
    BROADCAST = "__ANY_RECEIVER__"
    RESERVED_WORDS = ["sender", "receiver", "dumpArgs"]
    
    def __init__(self, sender, receiver, **messageArgs):
        self._sender = sender
        self._receiver = receiver
        self._messageArgs = messageArgs
        
        argReprs = []
        for arg in messageArgs:
            if arg.startswith("_"):
                raise Exception("Cannot construct message arguments that begin with '_'")
            if arg in self.RESERVED_WORDS:
                raise Exception("Message cannot have an argument {} because reserved".format(arg))
            setattr(self, arg, messageArgs[arg])
            argReprs.append("{}={}".format(arg, messageArgs[arg]))
            
        self._repr = "{mtype} {sender}->{receiver}({args})".format(mtype=self.__class__,
                                                                   sender=sender,
                                                                   receiver=receiver,
                                                                   args=",".join(argReprs)
                                                                   )
            
    def __repr__(self):
        return self._repr 
    
    def sender(self): return self._sender
    def receiver(self): return self._receiver
    def dumpArgs(self): return self._messageArgs
    
class Event(GameMessage):
    pass

class Request(GameMessage):
    pass

class Response(GameMessage):
    @classmethod
    def FromRequest(cls, req, value, isError=False):
        return cls(req.receiver(), req.sender(), value, isError)
    
    def __init__(self, sender, receiver, value, isError=False):
        super().__init__(sender, receiver, Value=value, IsError=isError)
        
    def __bool__(self):
        return not self.IsError
    
    #def __repr__(self):
    #    return str(self.Value)
    
class Failure(Response):
    @classmethod
    def FromRequest(cls, req, value):
        return cls(req.receiver(), req.sender(), value)
    
    def __init__(self, sender, receiver, errorMessage):
        super().__init__(sender, receiver, errorMessage, isError=True)