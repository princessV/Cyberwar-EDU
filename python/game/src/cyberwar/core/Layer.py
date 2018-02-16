'''
Created on Feb 12, 2018

@author: seth_
'''

from .messages import GameMessage, Request, Response, Failure, Event

import logging
logger = logging.getLogger(__name__)

class StartGameRequest(Request):
    def __init__(self, sender):
        super().__init__(sender, Request.BROADCAST)

class Layer:
    REGISTERED_NAMES = {}
    
    def __init__(self, name, lowerLayer=None):
        if name in self.REGISTERED_NAMES:
            raise Exception("Cannot create layer named {}. Already exists.".format(name))
        self._name = name
        self._lowerLayer = lowerLayer
        self._upperLayer = None
        self._cleanup = []
        
        if lowerLayer:
            lowerLayer._upperLayer = self
            
    def _startup(self, req):
        return self._requestAcknowledged(req, "{} startup complete".format(self._name))
    
    def registerCleanup(self, f, description=None):
        if description==None:
            description = "cleanup_task_{}".format(len(self._cleanup)+1)
        self._cleanup.append((description, f))
            
    def name(self):
        return self._name
        
    def _requestAcknowledged(self, req, message="Acknowledged", ackType=Response):
        return ackType.FromRequest(req, message)
    
    def _requestFailed(self, req, message="Failed", failureType=Failure):
        # todo, assert that failureType is subclass of Failure
        return failureType.FromRequest(req, message)
        
    def _handleRequest(self, req):
        return self._requestedFailed(req, "Not Implemented")
    
    def _handleEvent(self, event):
        pass # Default behavior is to ignore event. TODO: Log?
        
    def send(self, m):
        if m.receiver() == self._name:#in [self._name, GameMessage.BROADCAST]:
            try:
                return self._handleRequest(m)
            except Exception as e:
                return self._requestFailed(m, str(e))
        elif m.receiver() == GameMessage.BROADCAST:
            try:
                # TODO: enforce start before anything else?
                if isinstance(m, StartGameRequest):
                    result = {self._name: self._startup(m)}
                else:
                    result = {self._name: self._handleRequest(m)}
            except Exception as e:
                result = {self._name: self._requestFailed(m, str(e))}
            
            if self._lowerLayer:
                result.update(self._lowerLayer.send(m))
            return result
        elif self._lowerLayer:
            return self._lowerLayer.send(m)
        else:
            return Failure(self._name, m.sender(), "Expected receiver {} not found.".format(m.receiver()))
    
    def receive(self, m):
        if m.receiver() in [self._name, GameMessage.BROADCAST]:
            try:
                self._handleEvent(m)
            except Exception as e:
                logger.debug("Event handling failed: {}".format(e))
            if self._upperLayer and m.receiver() == GameMessage.BROADCAST:
                self._upperLayer.receive(m)
        elif self._upperLayer:
            self._upperLayer.receive(m)
        else:
            logger.debug("Expected event receiver {} not found".format(m.receiver()))
            
    def raiseEvent(self, event):
        if self._upperLayer:
            self._upperLayer.receive(event)
            
    def cleanup(self):
        for description, f in self._cleanup:
            print("Cleanup Task: {}".format(description)) # TODO: replace print with something...
            try:
                f()
            except:
                pass # TODO: log cleanup errors
        if self._lowerLayer:
            self._lowerLayer.cleanup()