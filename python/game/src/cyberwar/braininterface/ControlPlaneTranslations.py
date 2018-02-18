
from .translations import MoveCommand, ScanCommand, BrainConnectCommand
from .translations import MobileAttributeInterface, ObserverAttributeInterface
from .translations import BrainConnectInterface, BrainConnectResponse
from .translations import FailureResponse, ResultResponse
from .translations import MoveCompleteEvent, ScanResponse, ObjectMoveEvent
from .translations import TangibleAttributeInterface, DamageEvent, StatusCommand, StatusResponse
from .translations import NetworkTranslator

from ..controlplane.objectdefinitions import Mobile, Observer, Tangible, NamedObject
from ..controlplane.Directions import Directions
from ..controlplane.objectdefinitions import ControlPlaneObject
from ..controlplane.Layer import ObjectMoveRequest, ObjectScanRequest
from ..controlplane.Layer import ObjectMoveCompleteEvent, ObjectScanResult, ObjectDamagedEvent

from ..terrain.types import BaseType as BaseTerrainType

from ..core.messages import Failure, Response, GameMessage

from ..core.Board import ChangeContentsEvent

GameMessageToNetworkMessage = {}


"""
translations.py is written generically, so it can be used anywhere in the client,
server, (or proxy). This file creates subclasses that work specifically with
the game server. They replace the base versions in the NetworkTranslator
so that unmarshalled objects have the extra functionality
"""

class ControlPlaneNetworkTranslator(NetworkTranslator):
    
    def __init__(self, *args):
        super().__init__(*args)
    
    # TODO: Improve. Very hacky.
    # this subclass changes marshall to accept a gameMessage
    # it convers this into a regular message.
    def marshallToNetwork(self, gameMessage):
        if isinstance(gameMessage, GameMessage):
            if gameMessage.__class__ in GameMessageToNetworkMessage:
                networkMessage = GameMessageToNetworkMessage[gameMessage.__class__].Translate(gameMessage)
            else:
                return super().marshallToNetwork(FailureResponse("Could not marshall game message {}".format(gameMessage)))    
        else:
            networkMessage = gameMessage
        return super().marshallToNetwork(networkMessage)

class ControlPlaneBrainConnectCommand(BrainConnectCommand):
    def handle(self, game, object):
        attributes = [a.identifier() for a in object.getAttributes()]
        return BrainConnectResponse(object.identifier(), attributes)
    
class GenericTranslator:
    @classmethod
    def Translate(self, message):
        if message:
            return ResultResponse(message.Value)
        else:
            return FailureResponse(message.Value)

BrainConnectInterface.COMMANDS = [ControlPlaneBrainConnectCommand]
GameMessageToNetworkMessage[Failure] = GenericTranslator
GameMessageToNetworkMessage[Response] = GenericTranslator

class ControlPlaneMoveCommand(MoveCommand):
    def handle(self, game, object):
        return game.send(ObjectMoveRequest(game.name(), 
                                           object, 
                                           Directions[self.direction]))
    
class MoveCompleteTranslator:
    @classmethod
    def Translate(cls, message):
        return MoveCompleteEvent(message.Location, message.Message)

MobileAttributeInterface.COMMANDS=[ControlPlaneMoveCommand]
GameMessageToNetworkMessage[ObjectMoveCompleteEvent]=MoveCompleteTranslator


class ControlPlaneScanCommand(ScanCommand):
    def handle(self, game, object):
        return game.send(ObjectScanRequest(game.name(),
                                           object))
        
class ScanResultTranslator:
    @classmethod
    def ObservableData(cls, object):
        data = []
        if isinstance(object, BaseTerrainType):
            data.append(("type","terrain"))
            data.append(("identifier",object.identifier()))
        elif isinstance(object, ControlPlaneObject):
            data.append(("type","object"))
            data.append(("identifier",object.identifier()))
            data.append(("attributes", ",".join([a.identifier() for a in object.getAttributes()])))
            for attribute in object.getAttributes():
                rawData = attribute.rawData()
                for k,v in rawData:
                    data.append((k, str(v)))
        else:
            data.append(("type","unknown"))
        return data
    
    @classmethod
    def Translate(cls, message):
        scanData = []
        for location, contents in message.Value:
            scanData.append((location, [cls.ObservableData(o) for o in contents]))
        return ScanResponse(scanData)
    
class ObjectMoveTranslator:
    @classmethod
    def Translate(cls, message):
        location = (message.X, message.Y)
        status = message.Operation # arrive/ depart
        objectIdentifier = message.Object.identifier()
        return ObjectMoveEvent(objectIdentifier, location, status)
        
ObserverAttributeInterface.COMMANDS=[ControlPlaneScanCommand]
GameMessageToNetworkMessage[ObjectScanResult] = ScanResultTranslator
GameMessageToNetworkMessage[ChangeContentsEvent] = ObjectMoveTranslator

class ControlPlaneStatusCommand(StatusCommand):
    def handle(self, game, object):
        return StatusResponse(ScanResultTranslator.ObservableData(object))

class ObjectDamageTranslator:
    @classmethod
    def Translate(cls, message):
        return DamageEvent(message.TargetObject.identifier(),
                                  message.Damage, message.TargetDamage,
                                  message.Message)
TangibleAttributeInterface.COMMANDS=[ControlPlaneStatusCommand]
GameMessageToNetworkMessage[ObjectDamagedEvent] = ObjectDamageTranslator