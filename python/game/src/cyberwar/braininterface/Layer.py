'''
Created on Feb 14, 2018

@author: seth_
'''

from ..core.messages import Request, Response
from ..core.Board import InitializeObjectRequest, ObjectChurnEvent
from ..core.Layer import Layer as LayerBase

from ..controlplane.objectdefinitions import ControlPlaneObject
from ..controlplane.Layer import ObjectObservationEvent, ObjectMoveCompleteEvent

from .connection import BrainConnectionProtocol
from .Loader import Loader, BrainEnabled

import asyncio, random

class CreateBrainControlledObjectRequest(Request):
    def __init__(self, sender, brainDir, *attributes):
        super().__init__(sender, BrainInterfaceLayer.LAYER_NAME,
                         BrainDir=brainDir, Attributes=attributes)
        
class CreateBrainControlledObjectResponse(Response):
    pass

class BrainInterfaceLayer(LayerBase):
    LAYER_NAME = "braininterface"
    SERVER_PORT = 10013
    
    def __init__(self, lowerLayer):
        super().__init__(self.LAYER_NAME, lowerLayer)
        self._objectToID = {}
        self._idToObject = {}
        
        coro = asyncio.get_event_loop().create_server(lambda: BrainConnectionProtocol(self, self), 
                                                      host="127.0.0.1",
                                                      port=self.SERVER_PORT)
        f = asyncio.ensure_future(coro)
        self.registerCleanup(BrainEnabled.ShutdownAll, "Shutdown all brain subprocesses")
        self.registerCleanup(lambda: f.result().close(), "Shutdown brain connections server")
        
    def getObjectByIdentifier(self, identifier):
        return Loader.GetObjectByBrainID(identifier)
    
    def _handleRequest(self, req):
        if isinstance(req, CreateBrainControlledObjectRequest):
            brainIdentifier = random.randint(1,2**32)
            brainAttr = BrainEnabled(req.BrainDir, brainIdentifier)
            object = ControlPlaneObject(brainAttr, *req.Attributes)
            
            # TODO: This needs to be rewritten. Unified with Loader
            Loader.BRAINID_TO_OBJECT[brainIdentifier] = object
            
            r = self._lowerLayer.send(InitializeObjectRequest(self._name,
                                                              object,
                                                              Loader.OBJECT_TYPE))
            if not r:
                return r
            return self._requestAcknowledged(req, object, ackType=CreateBrainControlledObjectResponse)
            # insert this onto the board. We do this 
        else:
            return self._requestFailed(req, "Unknown Request")
        
    def _handleEvent(self, event):
        if isinstance(event, ObjectChurnEvent):
            if event.Operation == ObjectChurnEvent.RELEASED and isinstance(event.Object, ControlPlaneObject):
                brainAttr = event.Object.getAttribute(BrainEnabled)
                if not brainAttr: return
                
                # It's one of ours! We need to stop the brain
                brainAttr.stop()
                # eventually auto-provision on insert, and delete on destruction 
                
        elif isinstance(event, ObjectObservationEvent):
            observer = event.Object
            BrainConnectionProtocol.HandleEvent(observer, event.Event)
            
        elif isinstance(event, ObjectMoveCompleteEvent):
            BrainConnectionProtocol.HandleEvent(event.Object, event)
Layer = BrainInterfaceLayer