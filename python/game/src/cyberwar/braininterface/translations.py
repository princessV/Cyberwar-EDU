'''
Created on Feb 14, 2018

@author: seth_
'''

"""
This version can be used by any client. A specialized version
in ControlPlanTranslations is used for the game system
"""

import pickle

class NetworkTranslator:
    AttributeInterfaces = {}
    
    @classmethod
    def RegisterAttributeInterface(cls, interface):
        cls.AttributeInterfaces[interface.ATTRIBUTE_NAME] = interface
    
    def __init__(self, *attributes):
        self._cmds = {}
        self._events = {}
        self._responses = {}
        
        installInterfaces = [BrainConnectInterface]
        
        for attrName in attributes:
            if attrName in self.AttributeInterfaces:
                installInterfaces.append(self.AttributeInterfaces[attrName])
        for interface in installInterfaces:
            print("loading interface", interface)
            for command in interface.COMMANDS:
                print("\tLoading command",command.CMD)
                self._cmds[command.CMD] = command
            for event in interface.EVENTS:
                self._events[event.EVENT] = event
            for response in interface.RESPONSES:
                self._responses[response.RESPONSE] = response
        
    def marshallToNetwork(self, message):
        if hasattr(message, "CMD"):
            return self._cmds[message.CMD].Marshall(message)
        elif hasattr(message, "RESPONSE"):
            return self._responses[message.RESPONSE].Marshall(message)
        elif hasattr(message, "EVENT"):
            return self._events[message.EVENT].Marshall(message)
        raise Exception("Unknown message type {}".format(message))
    
    def processHeader(self, message):
        lines = message.split(b"\n")
        if len(lines) == 0:
            raise Exception("No Message")
        mType, msg, version = lines[0].split(b" ")
        if version != b"braininterface/1.0":
            raise Exception("Wrong version")
        
        headers = {}
        for line in lines[1:]:
            k,v = line.split(b":")
            headers[k.strip()] = v.strip()
        return mType, msg, headers
   
    def unmarshallFromNetwork(self, mType, msg, headers, body):
        if mType == b"CMD":
            translations = self._cmds
        elif mType == b"EVENT":
            translations = self._events
        elif mType == b"RESPONSE":
            translations = self._responses
        else:
            raise Exception("Unknown Message Type {}".format(mType))
        if msg not in translations:
            raise Exception("Unknown {} {}".format(mType, msg))
        
        return translations[msg].Unmarshall(headers, body)

class BrainConnectCommand:
    CMD = b"__connect__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD __connect__ braininterface/1.0\n"
        message += b"Object_identifier: " + "{}".format(cmd.objectIdentifier).encode()+b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
        
    @classmethod
    def Unmarshall(cls, headers, body):
        identifier = int(headers[b"Object_identifier"])
        return cls(identifier)
    
    def __init__(self, objectIdentifier):
        self.objectIdentifier = objectIdentifier
        
class BrainConnectResponse:
    RESPONSE = b"__connect_response__"
    
    @classmethod
    def Marshall(cls, cmd):
        body = pickle.dumps(cmd.attributes)
        bodyLength = "{}".format(len(body))
        message = b"RESPONSE __connect_response__ braininterface/1.0\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        attributes = pickle.loads(body)
        return cls(attributes)
    
    def __init__(self, attributes):
        self.attributes = attributes
        
class FailureResponse:
    RESPONSE = b"__failure__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"RESPONSE __failure__ braininterface/1.0\n"
        message += b"Message: " + cmd.message.encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(headers[b"Message"].decode())
    
    def __init__(self, message):
        self.message = message
    
class ResultResponse:
    RESPONSE = b"generic_response"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"RESPONSE generic_response braininterface/1.0\n"
        message += b"Message: " + cmd.message.encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(headers[b"Message"].decode())
    
    def __init__(self, message):
        self.message = message
        
class BrainConnectInterface:
    ATTRIBUTE_NAME = "__default__"
    COMMANDS = [BrainConnectCommand]
    RESPONSES = [BrainConnectResponse, FailureResponse, ResultResponse]
    EVENTS = []
NetworkTranslator.RegisterAttributeInterface(BrainConnectInterface)

class MoveCommand:
    CMD = b"move"
    
    @classmethod
    def Marshall(cls, cmd):
        directionName = cmd.direction.encode()
        message = b"CMD move braininterface/1.0\n"
        message += b"Direction: " + directionName + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n" # END
        return message
        
    @classmethod
    def Unmarshall(cls, headers, body):
        directionName = headers[b"Direction"].decode()
        return cls(directionName)

    def __init__(self, direction):
        self.direction = direction

class MoveCompleteEvent:
    EVENT = b"move_complete"
    
    @classmethod
    def Marshall(cls, event):
        body = pickle.dumps(event.location)
        bodyLength = "{}".format(len(body))
        message = b"EVENT move_complete braininterface/1.0\n"
        message += b"Message: "+event.message.encode()+b"\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        location = pickle.loads(body)
        return cls(location, headers[b"Message"].decode())
    
    def __init__(self, location, message):
        self.location = location
        self.message = message
        
class MobileAttributeInterface:
    ATTRIBUTE_NAME = "mobile"
    COMMANDS = [MoveCommand]
    EVENTS = [MoveCompleteEvent]
    RESPONSES = []
NetworkTranslator.RegisterAttributeInterface(MobileAttributeInterface)
        
class ScanCommand:
    CMD = b"scan"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD scan braininterface/1.0\n"
        message += b"Content_length: 0\n"
        message += b"\n" # END
        return message
        
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls()
    
class ScanResponse:
    RESPONSE = b"scan_response"
    
    @classmethod
    def Marshall(cls, cmd):
        body = pickle.dumps(cmd.scanResults)
        bodyLength = "{}".format(len(body))
        message = b"RESPONSE scan_response braininterface/1.0\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        scanResults = pickle.loads(body)
        return cls(scanResults)
        
    def __init__(self, scanResults):
        self.scanResults = scanResults
        
class ObjectMoveEvent:
    EVENT = b"object_moved"
    
    @classmethod
    def Marshall(cls, event):
        body = pickle.dumps((event.objectIdentifier, event.location))
        bodyLength = "{}".format(len(body))
        message = b"EVENT object_moved braininterface/1.0\n"
        message += b"Status: "+event.status.encode()+b"\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        objectIdentifier, location = pickle.loads(body)
        return cls(objectIdentifier,
                   location,
                   headers[b"Status"].decode())
    
    def __init__(self, objectIdentifier, location, status):
        self.objectIdentifier = objectIdentifier
        self.location = location
        self.status = status

class ObserverAttributeInterface:
    ATTRIBUTE_NAME = "observer"
    COMMANDS = [ScanCommand]
    RESPONSES = [ScanResponse]
    EVENTS = []
NetworkTranslator.RegisterAttributeInterface(ObserverAttributeInterface)