'''
Created on Feb 13, 2018

@author: seth_
'''

from ..core.messages import Request, Response, Event
from ..core.Board import ContentsRequest, LocateRequest, PutRequest, RemoveRequest, ObjectChurnEvent
from ..core.Board import ChangeContentsEvent, DimensionsRequest, ReleaseObjectRequest
from ..core.Board import DereferenceObjectPointerRequest, DereferenceObjectPointerResponse
from ..core.Layer import Layer as LayerBase

from .objectdefinitions import ControlPlaneObject
from .objectdefinitions import Observer, Mobile, Tangible, Technician
from .RangedLookup import RangedLookup
from .Directions import Directions

from ..terrain.types import *

import asyncio, random

# REQUESTS
class ObjectScanRequest(Request):
    def __init__(self, sender, object):
        super().__init__(sender, ControlLayer.LAYER_NAME,
                         Object = object)

class ObjectMoveRequest(Request):
    def __init__(self, sender, object, direction):
        super().__init__(sender, ControlLayer.LAYER_NAME, 
                         Object=object, 
                         Direction=direction)
        
class ObjectRepairRequest(Request):
    def __init__(self, sender, object, repairTarget):
        super().__init__(sender, ControlLayer.LAYER_NAME,
                         Object=object,
                         RepairTarget=repairTarget)
        
# TODO: Add a resource changing request

class ObjectScanResult(Response): pass

class ObjectMoveCompleteEvent(Event):
    def __init__(self, receiver, object, newLocation, message):
        super().__init__(ControlLayer.LAYER_NAME, receiver, 
                         Object=object, Location=newLocation, Message=message)
        
class ObjectDamagedEvent(Event):
    def __init__(self, receiver, object, targetObject, damage, targetDamage, message):
        super().__init__(ControlLayer.LAYER_NAME, receiver, 
                         Object=object, TargetObject=targetObject,
                         Damage=damage, TargetDamage=targetDamage,
                         Message=message)

class ObjectRepairCompleteEvent(Event):
    def __init__(self, receiver, object, repairTarget, amountRepaired, message):
        super().__init__(ControlLayer.LAYER_NAME, receiver,
                         Object=object, RepairTarget=repairTarget,
                         AmountRepaired=amountRepaired, Message=message)
        
class ObjectObservationEvent(Event):
    """This event is when a specific object
    observes a broadcast event. Used in passing
    up to higher layers that a specific object
    is aware of something."""
    def __init__(self, receiver, object, event):
        super().__init__(ControlLayer.LAYER_NAME, receiver, 
                         Object=object, Event=event)
        

class ControlLayer(LayerBase):
    LAYER_NAME = "control"
    
    def __init__(self, lowerLayer):
        super().__init__(self.LAYER_NAME, lowerLayer)
        self._observerTracking = RangedLookup()
        #self._moveTracking = {}
        self._repairTracking = {}
        self._repairTargetTracking = {}
    
    def _handleRequest(self, req):
        if isinstance(req, ObjectScanRequest):
            
            # We track observer locations, so no need to ask game board
            # Moreover, only observers can observe. So we should handle this anyway
            currentLocation = self._observerTracking.getLocation(req.Object)
            if currentLocation is None:
                # either we dont' have this object or it's not on the board
                # We could return an error or return nothing.
                # let's return an error
                return self._requestFailed(req, "Object is not an observer or has no location")
            
            dimensionsResult = self._lowerLayer.send(DimensionsRequest(self.LAYER_NAME))
            maxX, maxY = dimensionsResult.Value
            
            scannedSquares = []
            obsAttr = req.Object.getAttribute(Observer)
            obsRange = obsAttr.range()
            
            # iterate x's and then y's. We want to return line-by-line
            for j in range(currentLocation[1]-obsRange, currentLocation[1]+obsRange+1):
                for i in range(currentLocation[0]-obsRange, currentLocation[0]+obsRange+1):
                    if i < 0 or i >= maxX or j < 0 or j >= maxY: continue
                    
                    result = self._lowerLayer.send(ContentsRequest(self.LAYER_NAME, i, j))
                    if not result:
                        return result # TODO: make this a message from our level
                    scanResults = [obsAttr.view(currentLocation, (i,j), obj) for obj in result.Value]
                    scannedSquares.append(((i,j), scanResults))
            return self._requestAcknowledged(req, scannedSquares, ackType=ObjectScanResult)
        elif isinstance(req, ObjectMoveRequest):
            if not isinstance(req.Object, ControlPlaneObject):
                return self._requestFailed(req, "Object not part of control pane")
            
            mobileAttr = req.Object.getAttribute(Mobile)
            if not mobileAttr:
                return self._requestFailed(req, "Object is not mobile.")
            
            if req.Direction not in Directions:
                return self._requestFailed(req, "Unknown direction")
            
            speed = mobileAttr.squaresPerSecond()
            if speed < .01: # TODO: Make this a constant somewhere. Minimum Speed
                return self._requestFailed(req, "Object speed reduced to zero. Cannot move.")
            
            delay = 1.0/speed
            
            #if not req.Object in self._moveTracking:
            #    self._moveTracking[req.Object] = []
                
            asyncio.get_event_loop().call_later(delay, 
                                                self._completeMove,
                                                req)
            
            return self._requestAcknowledged(req, "Move scheduled")
        
        elif isinstance(req, ObjectRepairRequest):
            if not isinstance(req.Object, ControlPlaneObject):
                return self._requestFailed(req, "Technician not part of control plane")
            
            if not isinstance(req.RepairTarget, ControlPlaneObject):
                return self._requestFailed(req, "Repair Target not part of control plane")
            
            technicianAttr = req.Object.getAttribute(Technician)
            if not technicianAttr:
                return self._requestFailed(req, "Object is not a technician")
            
            repairTargetTangibleAttr = req.RepairTarget.getAttribute(Tangible)
            if not repairTargetTangibleAttr:
                return self._requestFailed(req, "Repair target is not tangible")
            
            result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, req.Object))
            if not result:
                return self._requestFailed(req, "Technician not on game board")
            
            technicianX, technicianY = result.Value
            
            result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, req.RepairTarget))
            if not result:
                return self._requestFailed(req, "Repair Target not on game board")
            
            repairTargetX, repairTargetY = result.Value
            
            if abs(technicianX-repairTargetX) > 1 or abs(technicianY-repairTargetY) > 1:
                return self._requestFailed(req, "Repair Target not close enough")
            
            if req.Object in self._repairTracking:
                return self._requestFailed(req, "Technician already repairing a target")
            
            # True indicates validity. If the technician or target move, will be set false
            self._repairTracking[req.Object] = True
            
            if req.RepairTarget not in self._repairTargetTracking:
                self._repairTargetTracking[req.RepairTarget] = set([])
            self._repairTargetTracking[req.RepairTarget].add(req.Object)
            
            asyncio.get_event_loop().call_later(technicianAttr.repairTime(), 
                                                self._completeRepair,
                                                req
                                                )
            
            return self._requestAcknowledged(req, "Repair scheduled")
             
        else:
            return self._requestFailed(req, "Unknown Request")
        
    def _isObserver(self, object):
        return isinstance(object, ControlPlaneObject) and object.getAttribute(Observer)
        
    def _handleEvent(self, event):
        if isinstance(event, ChangeContentsEvent):
            if event.Operation == ChangeContentsEvent.INSERT:
                
                # Is this an Observer? If so, track it
                if self._isObserver(event.Object):
                    self._observerTracking.observe(event.Object, (event.X, event.Y))
                
            elif event.Operation == ChangeContentsEvent.REMOVE:
                if self._isObserver(event.Object):
                    self._observerTracking.stopObserving(event.Object, (event.X, event.Y))
                    
                # if technician or repair target moved, set repair tracking false
                if event.Object in self._repairTracking:
                    self._repairTracking[event.Object] = False
                if event.Object in self._repairTargetTracking:
                    for technician in self._repairTargetTracking[event.Object]:
                        if technician in self._repairTracking:
                            self._repairTracking[technician] = False
                    del self._repairTargetTracking[event.Object]
                    
            if self._upperLayer:
                observers = self._observerTracking.getObserversInRange((event.X, event.Y))
                for observer in observers:
                    if observer == event.Object: continue
                    self._upperLayer.receive(ObjectObservationEvent(Event.BROADCAST,
                                                                    observer,
                                                                    event))
                    
                
    def _completeMove(self, request):
        # start by getting the location of the object.
        result = self._lowerLayer.send(LocateRequest(self.LAYER_NAME, request.Object))
        if not result:
            if self._upperLayer:
                self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                 request.Object,
                                                                 None,
                                                                 "Object not on game board"
                                                                 ))
            return

        objectLocation = result.Value
        newLocation = request.Direction.getSquare(objectLocation)

        contentsResult = self._lowerLayer.send(ContentsRequest(self.LAYER_NAME,
                                                               newLocation[0],
                                                               newLocation[1]))
        contents = contentsResult.Value
        for obj in contents:
            if isinstance(obj, Water):

                # check if the object if waterable

                myMobileAttr = request.Object.getAttribute(Mobile)
                if myMobileAttr.waterAble() == 2:
                    # change this to myMobileAttr.waterAble() == 0 to stop tank and rover move into water

                    errorMessage = "Could not move to {} because '{}'".format(objectLocation,
                                                                              "can not move into water")
                    if self._upperLayer:
                        self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                         request.Object,
                                                                         objectLocation,
                                                                         errorMessage
                                                                         ))
                    return

                    # my add end
        

        
        # if we're tangible, check for collisions:
        myTangibleAttr = request.Object.getAttribute(Tangible) 
        if myTangibleAttr:
            contentsResult = self._lowerLayer.send(ContentsRequest(self.LAYER_NAME,
                                                                   newLocation[0],
                                                                   newLocation[1]))
            if not contentsResult:
                errorMessage = "Could not move to {} because '{}'".format(objectLocation,
                                                                          contentsResult.Value)
                if self._upperLayer:
                    self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                     request.Object,
                                                                     objectLocation,
                                                                     errorMessage
                                                                     ))
                return
            
            contents = contentsResult.Value
            for object in contents:
                if isinstance(object, ControlPlaneObject):
                    objectTangibleAttr = object.getAttribute(Tangible)
                    if objectTangibleAttr:
                        # Two tangible objects in the same space. Collision
                        # for now, damge is 10% of hit points. Later, adjust by speed
                        maxMyDamage = int(objectTangibleAttr.hitpoints()/10)
                        maxObjectDamage = int(myTangibleAttr.hitpoints()/10)
                        
                        if maxMyDamage > 0:
                            myDamage = random.randint(1, maxMyDamage)
                            myTangibleAttr.takeDamage(myDamage)
                        else:
                            myDamage = 0
                            
                        if maxObjectDamage > 0:
                            objectDamage = random.randint(1, maxObjectDamage)
                            objectTangibleAttr.takeDamage(objectDamage)
                        else:
                            objectDamage = 0
                        
                        if objectTangibleAttr.hitpoints() == 0:
                            self._lowerLayer.send(ReleaseObjectRequest(self.LAYER_NAME,
                                                                       object))
                        if myTangibleAttr.hitpoints() == 0:
                            self._lowerLayer.send(ReleaseObjectRequest(self.LAYER_NAME,
                                                                       request.Object))
                        
                        if self._upperLayer:
                            objectName = object.identifier()
                            myName = request.Object.identifier()
                            
                            # Don't know whom should receive the damage report.
                            # BROADCAST
                            
                            self._upperLayer.receive(ObjectDamagedEvent(Event.BROADCAST,
                                                                        object, request.Object, 
                                                                        objectDamage, myDamage,
                                                                        "Collision with {}".format(myName))
                                                                        )
                            self._upperLayer.receive(ObjectDamagedEvent(Event.BROADCAST,
                                                                        request.Object, object,
                                                                        myDamage, objectDamage,
                                                                        "Collision with {}".format(objectName))
                                                                        )
                            self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                             request.Object,
                                                                             objectLocation,
                                                                             "Movement failed because of collision"))
                            return
        # move object
        moveResult = self._lowerLayer.send(PutRequest(self.LAYER_NAME,
                                                      newLocation[0],
                                                      newLocation[1],
                                                      request.Object))
        if not moveResult:
            errorMessage = "Could not move to {} because '{}'".format(objectLocation,
                                                                      moveResult.Value)
            if self._upperLayer:
                self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                 request.Object,
                                                                 objectLocation,
                                                                 errorMessage
                                                                 ))
            return
        
        if self._upperLayer:
            self._upperLayer.receive(ObjectMoveCompleteEvent(request.sender(),
                                                                 request.Object,
                                                                 newLocation,
                                                                 "Move successful"
                                                                 ))
    def _completeRepair(self, request):
        if self._repairTracking.get(request.Object, False):
            technicianAttr = request.Object.getAttribute(Technician)
            repairTangibleAttr = request.RepairTarget.getAttribute(Tangible)
            origHp = repairTangibleAttr.hitpoints()
            repairTangibleAttr.repair(technicianAttr.repairAmount())
            repairAmount = repairTangibleAttr.hitpoints() - origHp
            event = ObjectRepairCompleteEvent(request.sender(), 
                                              request.Object, 
                                              request.RepairTarget, 
                                              repairAmount, 
                                              "Repair successful")
        else:
            event = ObjectRepairCompleteEvent(request.sender(), 
                                              request.Object, 
                                              request.RepairTarget, 
                                              0, 
                                              "Repair failed, probably because connection broken")
        if request.RepairTarget in self._repairTargetTracking:
            if request.Object in self._repairTargetTracking[request.RepairTarget]:
                self._repairTargetTracking[request.RepairTarget].remove(request.Object)
            if len(self._repairTargetTracking[request.RepairTarget]) == 0:
                del self._repairTargetTracking[request.RepairTarget]
        if request.Object in self._repairTracking:
            del self._repairTracking[request.Object]
        if self._upperLayer:
            self._upperLayer.receive(event)
                    
Layer = ControlLayer