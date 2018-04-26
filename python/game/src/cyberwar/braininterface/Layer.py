'''
Created on Feb 14, 2018

@author: seth_
'''
from ..core.Board import InitializeObjectRequest, ObjectChurnEvent, PutRequest, LookupObject
from ..core.Layer import Layer as LayerBase

from ..controlplane.objectdefinitions import ControlPlaneObject, Tangible
from ..controlplane.Layer import ObjectObservationEvent, ObjectMoveCompleteEvent
from ..controlplane.Layer import ObjectDamagedEvent, LocateRequest, ObjectRepairCompleteEvent

from .connection import BrainConnectionProtocol
from .BotBuilder import BotBuilder
from .Loader import Loader, BrainEnabled
from .messages import *

import asyncio, random, io, tarfile, os


class BrainInterfaceLayer(LayerBase):
    LAYER_NAME = BRAIN_INTERFACE_LAYER_NAME
    SERVER_PORT = 10013
    
    # TODO: This should be a parameter to an attribute.
    # For now, hard coded to 10 seconds per hit point
    BRAIN_IO_SPEED=10
    
    def __init__(self, lowerLayer):
        super().__init__(self.LAYER_NAME, lowerLayer)
        self._objectToID = {}
        self._idToObject = {}
        self._brainIOTracking = {}
        self._brainIOTargetTracking = {}
        self._brainConnectionServer = None
        
        coro = asyncio.get_event_loop().create_server(lambda: BrainConnectionProtocol(self, self), 
                                                      host="127.0.0.1",
                                                      port=self.SERVER_PORT)
        f = asyncio.ensure_future(coro)
        f.add_done_callback(self._serverStarted)
        self.registerCleanup(BrainEnabled.ShutdownAll, "Shutdown all brain subprocesses")
        self.registerCleanup(self._serverShutdown, "Shutdown brain connections server")
        
    def _serverStarted(self, result):
        self._brainConnectionServer = result.result()
        # TODO: This is a hack. Find something better
        Loader.CAN_LAUNCH_BRAINS = True
        for brainAttr in BrainEnabled.LOAD_REQUIRED:
            brainAttr.start()
        BrainEnabled.LOAD_REQUIRED = []

    def _serverShutdown(self):
        if self._brainConnectionServer:
            self._brainConnectionServer.close()
        
    def getObjectByIdentifier(self, identifier):
        return Loader.GetObjectByBrainID(identifier)
    
    def _brainIoCheck(self, technician, target):
        if not isinstance(technician, ControlPlaneObject):
            return False, "Technician not part of control plane"
        
        if not isinstance(target, ControlPlaneObject):
            return False, "Brain IO Target not part of control plane"
        
        if not technician.getAttribute(BrainEnabled):
            return False, "Technician is not brain enabled"
        
        if not target.getAttribute(BrainEnabled):
            return False, "Brain IO target has no brain"
        
        result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, technician))
        if not result:
            return False, "Technician not on game board"
        
        technicianX, technicianY = result.Value
        
        result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, target))
        if not result:
            return False, "Repair Target not on game board"
        
        targetX, targetY = result.Value
        
        if abs(technicianX-targetX) > 1 or abs(technicianY-targetY) > 1:
            return False,"Repair Target not close enough"
        
        return True, ""
    
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
            
        elif isinstance(req, CreateBotRequest):
            if not isinstance(req.Builder, ControlPlaneObject) or req.Builder.getAttribute(BotBuilder) == None:
                return self._requestFailed(req, "Requested object is not a builder")
            
            result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, req.Builder))
            if not result:
                return False, "Technician not on game board"
            
            startX, startY = req.Direction.getSquare(result.Value)
            botBuilderAttr = req.Builder.getAttribute(BotBuilder)
            
            # TODO: fixed number of bots right now
            liveBuiltBotCount = 0
            for botId in botBuilderAttr.builtBots():
                botObj = LookupObject(self._lowerLayer, botId)
                if botObj:
                    if self._lowerLayer.send(LocateRequest(self.LAYER_NAME, botObj)):
                        liveBuiltBotCount += 1
                        
            if liveBuiltBotCount > 2:
                return self._requestFailed(req, "Too many bots built already.")
            try:
                bot = botBuilderAttr.buildBot(req.DesignName, req.Name, req.Address, req.BrainZip)
            except Exception as e:
                return self._requestFailed(req, str(e))
            brainAttr = bot.getAttribute(BrainEnabled)
            
            Loader.BRAINID_TO_OBJECT[brainAttr.brainIdentifier()] = bot
            
            r = self._lowerLayer.send(InitializeObjectRequest(self._name,
                                                              bot,
                                                              Loader.OBJECT_TYPE))
            if not r:
                return r
            
            r = self._lowerLayer.send(PutRequest(self.LAYER_NAME, startX, startY, bot))
            if not r:
                raise Exception(r.Value)
            
            return self._requestAcknowledged(req, bot.numericIdentifier(), ackType=CreateBotResponse)
        elif isinstance(req, GetBrainObjectByIdentifier):
            obj = LookupObject(self._lowerLayer, req.Identifier)
            # TODO, make sure it's a brain
            if not obj:
                return self._requestFailed(req, "Unknown object")
            else:
                return self._requestAcknowledged(req, obj, ackType=GetBrainObjectResponse)
            
        # The BrainIO Operations should be moved to their own ControlPlaneAttribute.
        elif isinstance(req, ReprogramBrainRequest) or isinstance(req, DownloadBrainRequest):
            reprogramOK, reason = self._brainIoCheck(req.Technician, req.Target)
            if not reprogramOK:
                return self._requestFailed(req, reason)
            
            if req.Technician in self._brainIOTracking:
                return self._requestFailed(req, "Technician already performing brain IO on a target")
            
            tangible = req.Target.getAttribute(Tangible)
            if not tangible:
                return self._requestFailed(req, "Target is not tangible")
            hp = tangible.hitpoints()
            
            # True indicates validity. If the technician or target move, will be set false
            self._brainIOTracking[req.Technician] = True
            
            if req.Target not in self._brainIOTargetTracking:
                self._brainIOTargetTracking[req.Target] = set([])
            self._brainIOTargetTracking[req.Target].add(req.Technician)
            
            asyncio.get_event_loop().call_later(self.BRAIN_IO_SPEED*hp, 
                                                self._brainIOComplete,
                                                req
                                                )
            
            return self._requestAcknowledged(req, "Brain IO scheduled")
        else:
            return self._requestFailed(req, "Unknown Request")
        
    def _reprogram(self, target, brain):
        try:
            brainAttr = target.getAttribute(BrainEnabled)
            file_obj = io.BytesIO(brain)
            tar = tarfile.open(fileobj = file_obj)
            for member in tar.getmembers():
                truePath = os.path.realpath(os.path.join(brainAttr.brainPath(), member.name))
                if not truePath.startswith(brainAttr.brainPath()):
                    # TODO: needs to be logged.
                    return False, "SecurityException: {} is an invalid path!".format(member.name)
            tar.extractall(path=brainAttr.brainPath())
            brainAttr.stop()
            asyncio.get_event_loop().call_later(2.0, brainAttr.start)
            return True, "Reprogramming Complete. Restart soon."
        except Exception as e:
            return b"", str(e)
    
    def _downloadBrain(self, target):
        try:
            brainAttr = target.getAttribute(BrainEnabled)
            rootPath = brainAttr.brainPath()
            tarMemory = io.BytesIO()
            tar = tarfile.open(fileobj=tarMemory, mode="w:gz")
            tar.add(rootPath, arcname="./")
            tar.close()
            return tarMemory.getvalue(), "Download Complete"
        except Exception as e:
            return b"", str(e)
        
    def _brainIOComplete(self, request):
        print("Brain IO complete")
        if self._brainIOTracking.get(request.Technician, False):
            if isinstance(request, ReprogramBrainRequest):
                reprogramOk, message = self._reprogram(request.Target, request.BrainZip)
                event = ReprogramBrainEvent(request.sender(),
                                            request.Technician,
                                            request.Target,
                                            reprogramOk,
                                            message)
            elif isinstance(request, DownloadBrainRequest):
                brainData, message = self._downloadBrain(request.Target)
                event = DownloadBrainEvent(request.sender(), 
                                              request.Technician, 
                                              request.Target,
                                              brainData,
                                              message)
            else: return
        else:
            if isinstance(request, ReprogramBrainRequest):
                event = ReprogramBrainEvent(request.sender(), request.Technician, request.Target, False,
                                            "Brain IO connection broken before reprogramming complete")
            elif isinstance(request, DownloadBrainRequest):
                event = DownloadBrainEvent(request.sender(), request.Technician, request.Target, False,
                                           "Brain IO connection broken before download complete")
            else: return
                
        if request.Target in self._brainIOTargetTracking:
            if request.Technician in self._brainIOTargetTracking[request.Target]:
                self._brainIOTargetTracking[request.Target].remove(request.Technician)
            if len(self._brainIOTargetTracking[request.Target]) == 0:
                del self._brainIOTargetTracking[request.Target]
        if request.Technician in self._brainIOTracking:
            del self._brainIOTracking[request.Technician]
            
        BrainConnectionProtocol.HandleEvent(event.Object, event)
        #if self._upperLayer:
        #    self._upperLayer.receive(event)
        
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
            
        elif isinstance(event, ObjectMoveCompleteEvent) or isinstance(event, ObjectDamagedEvent):
            if event.Object in self._brainIOTracking:
                self._brainIOTracking[event.Object] = False # moved or damanged, IO stops
            elif event.Object in self._brainIOTargetTracking:
                for technician in self._brainIOTargetTracking[event.Object]:
                    self._brainIOTracking[technician] = False
                del self._brainIOTargetTracking[event.Object]
            BrainConnectionProtocol.HandleEvent(event.Object, event)
        elif isinstance(event, ObjectRepairCompleteEvent):
            BrainConnectionProtocol.HandleEvent(event.Object, event)
            
Layer = BrainInterfaceLayer