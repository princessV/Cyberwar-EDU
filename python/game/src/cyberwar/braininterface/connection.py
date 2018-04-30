'''
Created on Feb 14, 2018

@author: seth_
'''

from ..core.messages import Failure, GameMessage
from ..controlplane.objectdefinitions import Mobile, Observer, Tangible
from ..controlplane.Directions import Directions
from .ControlPlaneTranslations import ControlPlaneNetworkTranslator as NetworkTranslator
from .ControlPlaneTranslations import ControlPlaneBrainConnectCommand as BrainConnectCommand
from .ControlPlaneTranslations import GameMessageToNetworkMessage


from .Loader import Loader, BrainEnabled

import asyncio



class BrainConnectionProtocol(asyncio.Protocol):
    OBJECT_LOOKUP = {}
    @classmethod
    def HandleEvent(cls, object, event):
        if object in cls.OBJECT_LOOKUP:
            try:
                cls.OBJECT_LOOKUP[object].send(event)
            except Exception as e:
                print("could not handle event for object {} because {}".format(object, e))
            
    def __init__(self, server, game):
        self.transport = None
        self.buffer = b""
        self.waitingMessage = None
        self.server = server
        self.game = game
        self.object = None
        self.translator = NetworkTranslator()
        
    def loadObject(self, identifier):
        self.object = self.server.getObjectByIdentifier(identifier)
        if not self.object: return
        
        if self.object in self.OBJECT_LOOKUP:
            self.transport.close()
            return
        self.OBJECT_LOOKUP[self.object] = self
        
        attributeStrings = []
        for attribute in self.object.getAttributes():
            attributeStrings.append(attribute.identifier())
        print("Attribute Strings", attributeStrings)
        
        self.translator = NetworkTranslator(*attributeStrings)
        
    def connection_made(self, transport):
        self.transport = transport
        
    def connection_lost(self, reason=None):
        if self.object in self.OBJECT_LOOKUP:
            del self.OBJECT_LOOKUP[self.object] 
        self.transport=None
            
    def handleEvent(self, event):
        try:
            self.send(event)
        except Exception as e:
            print ("could not send event {} because {}".format(event, e))
        
    def data_received(self, data):
        self.buffer += data
        
        while True:
            if self.waitingMessage is None:
                if b"\n\n" in self.buffer:
                    
                    index = self.buffer.index(b"\n\n")
                    message = self.buffer[:index]
                    self.buffer = self.buffer[index+2:]
                    
                    self.waitingMessage = self.translator.processHeader(message)
                    
                else:
                    return # done for now.
            
            else:
                headerType, headerArg, headers = self.waitingMessage
                contentLength = int(headers.get(b"Content_length", "0"))
                
                if len(self.buffer) < contentLength:
                    return # done for now
                
                body = self.buffer[:contentLength]
                self.buffer = self.buffer[contentLength:]
                self.waitingMessage = None
                    
            
                try:
                    #print("Try to get cmd")
                    cmd = self.translator.unmarshallFromNetwork(headerType, headerArg, headers, body)
                    if self.object is None:
                        # FIRST CMD MUST BE CONNECT!
                        if isinstance(cmd, BrainConnectCommand):
                            self.loadObject(cmd.objectIdentifier)
                        if self.object is None:
                            self.transport.close()
                            return
                    response = cmd.handle(self.game, self.object)
                    #print("Got response", response)
                except Exception as e:
                    print("Failed", e)
                    response = Failure(self.game.name(), "brain", "Could not execute. {}".format(e))
                self.send(response)    
            
    
    def send(self, message):
        data = self.translator.marshallToNetwork(message)
        #print("converted to data. Send {} bytes".format(len(data)))
        self.transport.write(data)