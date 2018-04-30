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
    
    @classmethod
    def HasHeader(cls, message):
        return b"\n\n" in message
    
    # TODO: Combine this with processHeader. Also, places in the code
    # like brain connection do their own version. Consolidate
    @classmethod
    def HasMessage(cls, message):
        if not cls.HasHeader(message): return False, None
        headerIndex = message.index(b"\n\n")
        mt, m, h = cls.processHeader(message[:headerIndex])
        blen = int(h.get(b"Content_length", 0))
        hOff = headerIndex +2
        if len(message[hOff:]) >= blen: return True, (mt, m, h, hOff, blen)
        return False, None
    
    @classmethod
    def processHeader(cls, message):
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
            raise Exception("Unknown {} {}. Options are {}".format(mType, msg, list(translations.keys())))
        
        return translations[msg].Unmarshall(headers, body)
    
class HeartbeatCommand:
    CMD = b"__heartbeat__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD __heartbeat braininterface/1.0\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
        
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls()


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
        body = pickle.dumps((cmd.identifier, cmd.attributes))
        bodyLength = "{}".format(len(body))
        message = b"RESPONSE __connect_response__ braininterface/1.0\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        identifier, attributes = pickle.loads(body)
        return cls(identifier, attributes)
    
    def __init__(self, identifier, attributes):
        self.identifier = identifier
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
        
class DownloadBrainCommand:
    CMD = b"__download_brain__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD __download_brain__ braininterface/1.0\n" 
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls()
    
class DownloadBrainResponse:
    RESPONSE = b"__download_brain_response__"
    
    @classmethod
    def Marshall(cls, cmd):
        body = cmd.data
        bodyLen = str(len(body)).encode()
        message = b"RESPONSE __download_brain_response__ braininterface/1.0\n"
        message += b"Content_length: " + bodyLen + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(body)
    
    def __init__(self, brainZip):
        self.data = brainZip
        
class ReprogramTargetCommand:
    CMD = b"__reprogram_target__"
    
    @classmethod
    def Marshall(cls, cmd):
        body = cmd.data
        bodyLen = str(len(body)).encode()
        message = b"CMD __reprogram_target__ braininterface/1.0\n"
        message += b"Target_identifier: " + str(cmd.targetIdentifier).encode() + b"\n"
        message += b"Content_length: " + bodyLen + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        targetIdentifier = int(headers[b"Target_identifier"])
        return cls(targetIdentifier, body)
    
    def __init__(self, targetIdentifier, brainZip):
        self.data = brainZip
        self.targetIdentifier = targetIdentifier
        
class ReprogramTargetEvent:
    EVENT = b"__reprogram_target_event__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"EVENT __reprogram_target_event__ braininterface/1.0\n"
        message += b"Target_identifier: " + str(cmd.targetIdentifier).encode() + b"\n"
        message += b"Success: " + (cmd.success and b"True" or b"False") + b"\n"
        message += b"Message: " + cmd.message.encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(int(headers[b"Target_identifier"]),
                   (headers[b"Success"] == b"True"),
                   headers[b"Message"].decode())
    
    def __init__(self, targetIdentifier, success, message):
        self.targetIdentifier = targetIdentifier
        self.success = success
        self.message = message
        
class DownloadTargetCommand:
    CMD = b"__download_target__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD __download_target__ braininterface/1.0\n"
        message += b"Target_identifier: " + str(cmd.targetIdentifier).encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        targetIdentifier = int(headers[b"Target_identifier"])
        return cls(targetIdentifier)
    
    def __init__(self, targetIdentifier):
        self.targetIdentifier = targetIdentifier
        
class DownloadTargetEvent:
    EVENT = b"__download_target_event__"
    
    @classmethod
    def Marshall(cls, cmd):
        body = cmd.brainZip
        bodyLen = str(len(body)).encode()
        message = b"EVENT __download_target_event__ braininterface/1.0\n"
        message += b"Message: " + cmd.message.encode() + b"\n"
        message += b"Target_identifier: " + str(cmd.targetIdentifier).encode() + b"\n"
        message += b"Content_length: " + bodyLen + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(int(headers[b"Target_identifier"]),
            headers[b"Message"].decode(),
                   body)
    
    def __init__(self, targetIdentifier, message, brainZip):
        self.targetIdentifier = targetIdentifier
        self.brainZip = brainZip
        self.message = message
        
class ReprogramCommand:
    CMD = b"__reprogram__"
    
    @classmethod
    def Marshall(cls, cmd):
        body = cmd.data
        bodyLen = str(len(body)).encode()
        message = b"CMD __reprogram__ braininterface/1.0\n"
        message += b"Path: " + cmd.path.encode() + b"\n"
        message += b"Restart_brain: " + (cmd.restartBrain and b"True" or b"False") + b"\n"
        message += b"Restart_networking: " + (cmd.restartNetworking and b"True" or b"False") + b"\n"
        message += b"Delete: " + (cmd.deleteFile and b"True" or b"False") + b"\n"
        message += b"Content_length: " + bodyLen + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        restartNetworking = (headers[b"Restart_networking"] == b"True") 
        restartBrain = (headers[b"Restart_brain"] == b"True") 
        deleteFile = (headers[b"Delete"] == b"True")
        return cls(headers[b"Path"].decode(),
                   body,
                   restartBrain,
                   restartNetworking,
                   deleteFile
                   )
    
    def __init__(self, path, data, restartBrain=False, restartNetworking=False, deleteFile=False):
        self.path = path
        self.data = data
        self.restartBrain = restartBrain
        self.restartNetworking = restartNetworking
        if deleteFile and len(self.data) > 0:
            raise Exception("Cannot delete a file that you are adding contents to")
        self.deleteFile = deleteFile
        
class ReprogramResponse:
    RESPONSE = b"__reprogram_response__"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"RESPONSE __reprogram_response__ braininterface/1.0\n"
        message += b"Path: " + cmd.path.encode() + b"\n"
        message += b"Success: " + (cmd.success and b"True" or b"False") + b"\n"
        message += b"Message: " + cmd.message.encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(headers[b"Path"].decode(), 
                   (headers[b"Success"] == b"True"),
                   headers[b"Message"].decode())
    
    def __init__(self, path, success, message):
        self.path = path
        self.success = success
        self.message = message
        
class BrainConnectInterface:
    ATTRIBUTE_NAME = "__default__"
    COMMANDS = [BrainConnectCommand, ReprogramCommand, DownloadBrainCommand,
                ReprogramTargetCommand, DownloadTargetCommand]
    RESPONSES = [BrainConnectResponse, FailureResponse, ResultResponse, 
                 ReprogramResponse, DownloadBrainResponse]
    EVENTS = [ReprogramTargetEvent, DownloadTargetEvent]
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
        #TODO: If event.message has a\n, this will break everything!!!!
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
    EVENTS = [ObjectMoveEvent]
NetworkTranslator.RegisterAttributeInterface(ObserverAttributeInterface)

class StatusCommand:
    CMD = b"status"
    
    @classmethod
    def Marshall(cls, event):
        message = b"CMD status braininterface/1.0\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls()
    
class StatusResponse:
    RESPONSE = b"status_response"
    
    @classmethod
    def Marshall(cls, event):
        body = pickle.dumps(event.data)
        bodyLength = str(len(body))
        message = b"RESPONSE status_response braininterface/1.0\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        data = pickle.loads(body)
        return cls(data)
    
    def __init__(self, observableData):
        self.data = observableData

class DamageEvent:
    EVENT = b"damage"
    
    @classmethod
    def Marshall(cls, event):
        body = pickle.dumps((event.targetObjectIdentifier, 
                             event.damage, event.targetDamage,
                             event.message))
        bodyLength = str(len(body))
        message = b"EVENT damage braininterface/1.0\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        targetObjectIdentifier, damage, targetDamage, message = pickle.loads(body)
        return cls(targetObjectIdentifier,
                   damage, targetDamage,
                   message)
        
    def __init__(self, targetObjectIdentifier, damage, targetDamage, message):
        self.targetObjectIdentifier = targetObjectIdentifier
        self.damage = damage
        self.targetDamage = targetDamage
        self.message = message

class TangibleAttributeInterface:
    ATTRIBUTE_NAME='tangible'
    COMMANDS = [StatusCommand]
    RESPONSES= [StatusResponse]
    EVENTS   = [DamageEvent]
NetworkTranslator.RegisterAttributeInterface(TangibleAttributeInterface)

class RepairCommand:
    CMD = b"repair"
    
    @classmethod
    def Marshall(cls, cmd):
        message = b"CMD "+cls.CMD+b" braininterface/1.0\n"
        message += b"Target_identifier: " + str(cmd.targetIdentifier).encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(int(headers[b"Target_identifier"]))
    
    def __init__(self, targetIdentifier):
        self.targetIdentifier = targetIdentifier
        
class RepairCompleteEvent:
    EVENT = b"repair_complete_event"
    
    @classmethod
    def Marshall(cls, event):
        message = b"EVENT "+cls.EVENT+b" braininterface/1.0\n"
        message += b"Target_identifier: " + str(event.targetIdentifier).encode() + b"\n"
        message += b"Amount_repaired: " + str(event.amountRepaired).encode() + b"\n"
        message += b"Message: " + event.message.encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(int(headers[b"Target_identifier"]), int(headers[b"Amount_repaired"]),
                   headers[b"Message"].decode())
    
    def __init__(self, targetIdentifier, amountRepaired, message):
        self.targetIdentifier = targetIdentifier
        self.amountRepaired = amountRepaired
        self.message = message
        
class TechnicianAttributeInterface:
    ATTRIBUTE_NAME='technician'
    COMMANDS = [RepairCommand]
    RESPONSES= []
    EVENTS   = [RepairCompleteEvent]
NetworkTranslator.RegisterAttributeInterface(TechnicianAttributeInterface)
        
class BuildBotCommand:
    CMD = b"build_bot"
    
    @classmethod
    def Marshall(cls, cmd):
        body = cmd.brainZip
        bodyLength = str(len(body))
        message = b"CMD "+cls.CMD+b" braininterface/1.0\n"
        message += b"Direction: " + cmd.direction.encode() + b"\n"
        message += b"Design_name: " + cmd.designName.encode() + b"\n"
        message += b"Name: " + cmd.name.encode() + b"\n"
        message += b"Address: " + cmd.address.encode() + b"\n"
        message += b"Content_length: " + bodyLength.encode() + b"\n"
        message += b"\n"
        message += body
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(headers[b"Direction"].decode(),
                   headers[b"Design_name"].decode(),
                   headers[b"Name"].decode(),
                   headers[b"Address"].decode(),
                   body)
    
    def __init__(self, direction, designName, name, address, brainZip):
        self.direction = direction
        self.designName = designName
        self.name = name
        self.address = address
        self.brainZip = brainZip
        
class BuildBotResponse:
    RESPONSE = b"build_bot_response"
    
    @classmethod
    def Marshall(cls, response):
        message = b"RESPONSE "+cls.RESPONSE+b" braininterface/1.0\n"
        message += b"Built_bot_identifier: " + str(response.builtBotIdentifier).encode() + b"\n"
        message += b"Content_length: 0\n"
        message += b"\n"
        return message
    
    @classmethod
    def Unmarshall(cls, headers, body):
        return cls(int(headers[b"Built_bot_identifier"]))
    
    def __init__(self, builtBotIdentifier):
        self.builtBotIdentifier = builtBotIdentifier
        
class BotbuilderAttributeInterface:
    ATTRIBUTE_NAME='botbuilder'
    COMMANDS = [BuildBotCommand]
    RESPONSES= [BuildBotResponse]
    EVENTS   = []
NetworkTranslator.RegisterAttributeInterface(BotbuilderAttributeInterface)