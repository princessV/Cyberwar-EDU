'''
Created on Feb 22, 2017

@author: sethjn
'''

import random

from threading import RLock, Condition
from playground_interface import BotClientEndpoint

from twisted.internet import reactor
from twisted.internet.protocol import Protocol, connectionDone, Factory

import time

class GameLoopCtx(object):
    def __init__(self):
        self.socket = PlaygroundOutboundSocket
        self.api = DummyAPI()
        
class DummyAPI(object):
    TERRAIN_GENERIC = "land"
    TERRAIN_FARM = "farmland"
    TERRAIN_CITY = "city"
    def __init__(self):
        self.__x = 50
        self.__y = 50
        self.__inventory = []
        self.__inventorySize = 5
        self.__manhattanSightRange = 5
        self.__blocking = False
        
        self.__locations = []
        for i in range(0,10):
            for j in range(0,10):
                self.__locations.append((self.TERRAIN_GENERIC, (i*10)+1, (j*10)+1, ((i+1)*10), ((j+1)*10)))
        
        self.__locations[0] = (self.TERRAIN_FARM, 1,1,10,10) # square in upper left corner
        self.__locations[-1]= (self.TERRAIN_CITY, 91,91,100,100) # square in lower left corner
        
        self.__objects = {}
        
        for i in range(0,20):
            x, y = random.randint(0,99), random.randint(0,99)
            if not self.__objects.has_key(x):
                self.__objects[x] = {}
            if not self.__objects[x].has_key(y):
                self.__objects[x][y] = {}
            self.__objects[x][y]["object-%d" % i] = 1
        self.__moveSpeed = 1 # second
        self.__lastMove = time.time()
        
        self.__workSpeed = 5
        self.__lastWork = time.time()
        
    def __within(self, x, y, borderX1, borderY1, borderX2, borderY2):
        return x >= borderX1 and x <= borderX2 and y >= borderY1 and y <= borderY2
    
    def blocking(self):
        return self.__blocking
    
    def setBlocking(self, blocking):
        self.__blocking = blocking
        
    def move(self, direction):
        moveWaitTime = time.time()-self.__lastMove
        if moveWaitTime < self.__moveSpeed:
            if self.__blocking:
                time.sleep(self.__moveSpeed-moveWaitTime)
            else:
                return False, "Can't move yet"
        newX = self.__x
        newY = self.__y
        if direction == "north": # go north
            newY = self.__y - 1
        elif direction == "south": # go south
            newY = self.__y + 1
        elif direction == "east": # go east
            newX = self.__x + 1
        elif direction == "west": # go west
            newX = self.__x - 1
        else:
            return False, "Can't move direction %s" % direction
        if newX < 0 or newX > 100:
            return False, "Attempt to move out of bounds (X)"
        if newY < 0 or newY > 100:
            return False, "Attempt to move out of bounds (Y)"
        self.__x = newX
        self.__y = newY
        self.__lastMove = time.time()
        return True, "Moved %s" % direction
    
    def location(self):
        return True, "%d,%d" % (self.__x, self.__y)
    
    def look(self):
        msg = ""
        X1,Y1,X2,Y2 = (self.__x-self.__manhattanSightRange,
                     self.__y-self.__manhattanSightRange,
                     self.__x+self.__manhattanSightRange,
                     self.__y+self.__manhattanSightRange)
        for locationType, locationX1, locationY1, locationX2, locationY2 in self.__locations:
            if X1 > locationX2: continue
            if Y1 > locationY2: continue
            if X2 < locationX1: continue
            if Y2 < locationY1: continue
            
            visibleX1 = X1 < locationX1 and str(locationX1) or str(X1)
            visibleY1 = Y1 < locationY1 and str(locationY1) or str(Y1)
            visibleX2 = X2 > locationX2 and str(locationX2) or str(X2)
            visibleY2 = Y2 > locationY2 and str(locationY2) or str(Y2)
            msg += "Terrain: %s [(%s,%s) to (%s,%s)]\n" % (locationType, visibleX1, visibleY1, visibleX2, visibleY2) 
        for objX, yMap in self.__objects.items():
            for objY, objData in yMap.items():
                for gameObj, count in objData.items():
                    if self.__within(objX, objY, X1, Y1, X2, Y2):
                        count = count > 1 and "x%d" % count or ""
                        msg += "Object: %s at (%s,%s) %s\n" % (gameObj, objX, objY, count)
        return True, msg
    
    def work(self):
        if len(self.__inventory) >= self.__inventorySize:
            return False, "Inventory full"
        
        
        workWaitTime = time.time()-self.__lastWork
        if workWaitTime < self.__workSpeed:
            if self.__blocking:
                time.sleep(self.__workSpeed-workWaitTime)
            else: return False, "Can't work yet"
        
        currentTerrainType = None
        for locationType, X1, Y1, X2, Y2 in self.__locations:
            if self.__within(self.__x, self.__y, X1, Y1, X2, Y2):
                currentTerrainType = locationType
                break
        if not currentTerrainType:
            return False, "Error with map. Unknown terrain type at %s, %s" % (self.__x, self.__y)
        if currentTerrainType == "farmland":
            self.__inventory.append("FOOD")
            self.__lastWork = time.time()
            return True, "Worked 1 FOOD"
        return False, "Can't work terrain type %s" % currentTerrainType
    
    def inventory(self):
        msg = ""
        for i in range(len(self.__inventory)):
            item = self.__inventory[i]
            msg += "Item %d: %s\n" % (i, item)
        return True, msg
    
    def unload(self):
        if not self.__inventory:
            return False, "Inventory already empty"
        if not self.__objects.has_key(self.__x):
            self.__objects[self.__x] = {}
        if not self.__objects[self.__x].has_key(self.__y):
            self.__objects[self.__x][self.__y] = {}
        while self.__inventory:
            obj = self.__inventory.pop()
            self.__objects[self.__x][self.__y][obj] = self.__objects[self.__x][self.__y].get(obj, 0) + 1 
        return True, "Inventory emptied (items lost. item drop not yet supported)"

class PlaygroundSocketProtocol(Protocol):
    def __init__(self):
        self.__messages = []
        self.__connected = False
        self.__lock = RLock()
        self.__readyCondition = Condition(self.__lock)
        
    def dataReceived(self, data):
        with self.__readyCondition:
            self.__messages.append(data)
            self.__readyCondition.notify()
        
    def connectionMade(self):
        with self.__lock:
            self.__connected = True
        Protocol.connectionMade(self)
        #self.__stateChangeListener.connectionMade(self.transport)
        
    def close(self):
        reactor.callFromThread(self.transport.loseConnection)
        with self.__readyCondition:
            self.__readyCondition.notifyAll()
        
    def connectionLost(self, reason=connectionDone):
        with self.__lock:
            self.__connected = False
        #self.__stateChangeListener.connectionLost(reason)
        Protocol.connectionLost(self, reason)
        
    def write(self, data):
        reactor.callFromThread(self.transport.write, data)
    
    def ready(self):
        with self.__lock:
            if self.__messages: return True
            return False
        
    def nextMessage(self):
        with self.__lock:
            if self.__messages: return self.__messages.pop(0)
            return None
        
    def waitForNextMessage(self, timeout=None):
        with self.__readyCondition:
            if not self.__messages:
                try:
                    self.__readyCondition.wait(timeout)
                except RuntimeError, e:
                    # This is an error we don't expect, but just fail silently
                    return None
            if self.__messages:
                return self.__messages.pop(0)
            return None
        
    def checkConnected(self):
        with self.__lock:
            return self.__connected

    
class PlaygroundSocketProtocolFactory(Factory):
    protocol = PlaygroundSocketProtocol
        
class PlaygroundOutboundSocket(object):
    
    PROTOCOL_STACK = None
    ORIGIN = None
    
    def __init__(self):
        self.__protocol = None
        self.__key = random.randint(0, (2**64)-1)
        
    def __connectCallback(self, protocol):
        self.__protocol = protocol
    
    def connect(self, addr, port):
        if addr == "ORIGIN_SERVER":
            if self.ORIGIN: addr = self.ORIGIN
            else: raise Exception("No Origin Server Specified")
        endpoint = BotClientEndpoint(addr, port)
        if PlaygroundOutboundSocket.PROTOCOL_STACK:
            
            # python weirdly won't let a class variable point to a regular function.
            # have to manually pass self as the first argument.
            print "Trying to connect using protocol stack"
            stack = PlaygroundOutboundSocket.PROTOCOL_STACK(self, PlaygroundSocketProtocolFactory())
        else:
            print "trying to connect raw"
            stack = PlaygroundSocketProtocolFactory()
        print "connect stack", stack
        d = endpoint.connect(stack)
        d.addCallback(self.__connectCallback)
    
    def recv(self, timeout=0):
        "Gets data. if timeout is 0, returns immediately (non blocking)"
        if not self.__protocol: return None
        if timeout == 0:
            return self.__protocol.nextMessage()
        else:
            return self.__protocol.waitForNextMessage(timeout=timeout)
    
    def send(self, data):
        if not self.__protocol: return 0
        self.__protocol.write(data)
        return len(data)
    
    def close(self):
        if self.__protocol and self.__protocol.checkConnected():
            self.__protocol.close() 
            self.__protocol = None
    
    def connected(self):
        if self.__protocol: 
            return self.__protocol.checkConnected()
        return False
    
    def ready(self):
        if self.__protocol: return self.__protocol.ready()
        return False
    
    def key(self):
        return self.__key