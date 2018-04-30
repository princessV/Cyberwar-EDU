
from .messages import Request, Response, Failure, Event
from .Layer import Layer

import sqlite3


# BOARD REQUESTS:
class DimensionsRequest(Request):
    def __init__(self, sender):
        super().__init__(sender, Board.LAYER_NAME)

class ContentsRequest(Request):
    def __init__(self, sender, x, y):
        super().__init__(sender, Board.LAYER_NAME, X=x, Y=y)

class InitializeObjectRequest(Request):
    def __init__(self, sender, object, objType):
        super().__init__(sender, Board.LAYER_NAME, Object=object, ObjType=objType)
        
class ReleaseObjectRequest(Request):
    def __init__(self, sender, object):
        super().__init__(sender, Board.LAYER_NAME, Object=object)

class PutRequest(Request):
    def __init__(self, sender, x, y, object):
        super().__init__(sender, Board.LAYER_NAME, X=x, Y=y, Object=object)

class RemoveRequest(Request):
    def __init__(self, sender, object):
        super().__init__(sender, Board.LAYER_NAME, Object=object)

class LocateRequest(Request):
    def __init__(self, sender, object):
        super().__init__(sender, Board.LAYER_NAME, Object=object)
        
class GetObjectPointerRequest(Request):
    def __init__(self, sender, object):
        super().__init__(sender, Board.LAYER_NAME, Object=object)
        
class DereferenceObjectPointerRequest(Request):
    def __init__(self, sender, objectType, objectId):
        super().__init__(sender, Board.LAYER_NAME, ObjectType=objectType, ObjectId=objectId)
        
class DereferenceIngameObjectPointerRequest(Request):
    def __init__(self, sender, objectId):
        super().__init__(sender, Board.LAYER_NAME, ObjectId=objectId)
        
def LookupObject(game, objId):
    resp = game.send(DereferenceIngameObjectPointerRequest("info", objId))
    if not resp: return None
    return resp.Value
        
# EVENTS
class ChangeContentsEvent(Event):
    INSERT = "insert"
    REMOVE = "remove"
    def __init__(self, x, y, operation, object):
        if operation not in [self.INSERT, self.REMOVE]:
            raise Exception("Unknown Change Contents Event operation {}".format(operation))
        super().__init__(Board.LAYER_NAME, Event.BROADCAST,
                         X=x, Y=y, Operation=operation,
                         Object=object)
        
class ObjectChurnEvent(Event):
    ADDED = "added"
    RELEASED = "released"
    def __init__(self, operation, object):
        if operation not in [self.ADDED, self.RELEASED]:
            raise Exception("Unknown Churn Event {}".format(operation))
        super().__init__(Board.LAYER_NAME, Event.BROADCAST,
                         Operation=operation, Object=object)


# BOARD REQUEST FAILURES:
class InvalidLocation(Failure):
    pass


# BOARD REQUEST RESPONSES:
class DimensionsResult(Response): pass

class ContentsResult(Response): pass

class InitializeResult(Response): pass

class ReleaseResult(Response): pass

class PutResult(Response): pass

class RemoveResult(Response): pass
        
class LocateResult(Response): pass

class GetObjectPointerResponse(Response): pass

class DereferenceObjectPointerResponse(Response): pass


class Board(Layer):
    LAYER_NAME = "GameBoard"
    
    @classmethod
    def InitializeDatabase(cls, db):
        db.execute("CREATE TABLE IF NOT EXISTS game_metadata (field TEXT, value TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS game_board (x INTEGER, y INTEGER, objType TEXT, objId INTEGER)")
        
    @classmethod
    def NewBoard(cls, db, xSize, ySize):
        # WARNING! THIS ERASES ALL GAME DATA!
        db.execute("DROP TABLE IF EXISTS game_metadata")
        db.execute("DROP TABLE IF EXISTS game_board")
        
        cls.InitializeDatabase(db)
        
        db.execute("INSERT INTO game_metadata VALUES('xsize', ?)", (xSize,))
        db.execute("INSERT INTO game_metadata VALUES('ysize', ?)", (ySize,))
    
    def __init__(self, db, objectStore):
        super().__init__(self.LAYER_NAME)
        self._inMemoryCache = {}
        self._db = db
        self._cursor = db.cursor
        self._objectStore = objectStore
        self._xSize = int(self._getMetadata("xsize"))
        self._ySize = int(self._getMetadata("ysize"))
        
        if self._xSize is None or self._ySize is None:
            raise Exception("Database for game board not initialized.")
        
    def _startup(self, req):
        for i in range(self._xSize):
            for j in range(self._ySize):
                c = self._db.execute("SELECT objType, objId from game_board WHERE x=? AND y=?",
                             (i, j))
                self._inMemoryCache[(i,j)] = set([])
                for row in c.fetchall():
                    objType, objId = row
                    object = self._objectStore.load(objType, objId)
                    self.raiseEvent(ChangeContentsEvent(i, j, ChangeContentsEvent.INSERT, object))
                    self._inMemoryCache[(i,j)].add(object)
        return super()._startup(req)
        
    def _getMetadata(self, field, default=None):
        c = self._db.execute("SELECT value FROM game_metadata WHERE field=?", (field,))
        res = c.fetchone()
        if not res: return default
        return res[0]
    
    def _handleRequest(self, req):
        if isinstance(req, ContentsRequest):
            return self.getContents(req)
        elif isinstance(req, InitializeObjectRequest):
            return self.initializeObject(req)
        elif isinstance(req, ReleaseObjectRequest):
            return self.releaseObject(req)
        elif isinstance(req, PutRequest):
            return self.putObject(req)
        elif isinstance(req, RemoveRequest):
            return self.removeObject(req)
        elif isinstance(req, LocateRequest):
            return self.locateObject(req)
        elif isinstance(req, DimensionsRequest):
            return self.getDimensions(req)
        elif isinstance(req, GetObjectPointerRequest):
            try:
                objType, objId = self._objectStore.getDatabasePointer(req.Object)
                return self._requestAcknowledged(req, (objType, objId), ackType=GetObjectPointerResponse)
            except Exception as e:
                # TODO: Only a not found execption should be acknowledged.
                return self._requestFailed(req, "No such object")
        elif isinstance(req, DereferenceObjectPointerRequest):
            try:
                object = self._objectStore.load(req.ObjectType, req.ObjectId)
                return self._requestAcknowledged(req, object, ackType=DereferenceObjectPointerResponse)
            except Exception as e:
                return self._requestFailed(req, "No such object")
        elif isinstance(req, DereferenceIngameObjectPointerRequest):
            object = self._objectStore.getIngameObject(req.ObjectId)
            if object:
                return self._requestAcknowledged(req, object, ackType=DereferenceObjectPointerResponse)
            else: return self._requestFailed(req, "No such object")
        return self._requestFailed(req, "Unknown Request {}".format(req))
        
    def validateLocation(self, x, y):
        if x < 0 or x >= self._xSize or y < 0 or y >= self._ySize:
            return False
        return True
    
    def getDimensions(self, req):
        return self._requestAcknowledged(req, (self._xSize, self._ySize),
                                         ackType=DimensionsResult)
        
    def getContents(self, getRequest):
        if not self.validateLocation(getRequest.X, getRequest.Y):
            errorMessage = "({},{}) not a legal location in board of size ({}, {})"
            errorMessage = errorMessage.format(getRequest.X,
                                               getRequest.Y,
                                               self._xSize,
                                               self._ySize)
            return self._requestFailed(getRequest, errorMessage, 
                                       failureType=InvalidLocation)
        
        contents = []
        location = (getRequest.X, getRequest.Y)
        if location in self._inMemoryCache:
            contents = self._inMemoryCache[location]
        else:
            c = self._db.execute("SELECT objType, objId from game_board WHERE x=? AND y=?",
                                 (getRequest.X, getRequest.Y))
            for row in c.fetchall():
                objType, objId = row
                object = self._objectStore.load(objType, objId)
                contents.append(object)
            self._inMemoryCache[location] = contents
            
        return self._requestAcknowledged(getRequest, 
                                         contents,
                                         ackType=ContentsResult)
        
    def initializeObject(self, initializeRequest):
        if self._objectStore.hasObject(initializeRequest.Object):
            return self._requestFailed(initializeRequest, "Object already exists in game")

        objId =self._objectStore.addObjectToGame(initializeRequest.ObjType,
                                                 initializeRequest.Object)
        
        if self._upperLayer:
            self._upperLayer.receive(ObjectChurnEvent(ObjectChurnEvent.ADDED, initializeRequest.Object))

        return self._requestAcknowledged(initializeRequest, objId, ackType=InitializeResult)
    
    def releaseObject(self, releaseRequest):
        if not self._objectStore.hasObject(releaseRequest.Object):
            return self._requestFailed(releaseRequest, "Object does not exist in game")
        self.removeObject(RemoveRequest(self.LAYER_NAME, releaseRequest.Object))
        try:
            self._objectStore.removeObjectFromGame(releaseRequest.Object)
        except Exception as e:
            return self._requestFailed(releaseRequest, "Could not remove from game. {}".format(e))
        if self._upperLayer:
            self._upperLayer.receive(ObjectChurnEvent(ObjectChurnEvent.RELEASED, releaseRequest.Object))
        return self._requestAcknowledged(releaseRequest, True, ackType=ReleaseResult)
    
    def putObject(self, putRequest):
        if not self.validateLocation(putRequest.X, putRequest.Y):
            errorMessage = "({},{}) not a legal location in board of size ({}, {})"
            errorMessage = errorMessage.format(putRequest.X,
                                               putRequest.Y,
                                               self._xSize,
                                               self._ySize)
            return self._requestFailed(putRequest, errorMessage, 
                                       failureType=InvalidLocation)
        
        try:
            objType, objId = self._objectStore.getDatabasePointer(putRequest.Object)
        except Exception as e:
            return self._requestFailed(putRequest, e)
        
        c = self._db.execute("SELECT x, y FROM game_board WHERE objType=? AND objId=?",
                             (objType, objId))
        moved = False
        for row in c.fetchall(): # SHOULD BE AT MOST ONE. TODO, check?
            oldX, oldY = row
            # Already on board. Move from x,y to put.X, put.Y
            
            # update the in memory cache
            if putRequest.Object in self._inMemoryCache.get((oldX, oldY), set([])):
                self._inMemoryCache[(oldX, oldY)].remove(putRequest.Object)
            if not (putRequest.X, putRequest.Y) in self._inMemoryCache:
                self._inMemoryCache[(putRequest.X, putRequest.Y)] = set([])
            self._inMemoryCache[(putRequest.X, putRequest.Y)].add(putRequest.Object)
            
            self._db.execute("UPDATE game_board set x=?, y=? WHERE objType=? AND objId=?",
                             (putRequest.X, putRequest.Y, objType, objId))
            
            self.raiseEvent(ChangeContentsEvent(oldX, oldY,
                                                ChangeContentsEvent.REMOVE,
                                                putRequest.Object))
            moved = True
            break # THERE SHOULD BE AT MOST ONE!!!!
        
        # Not already on the board. Adding
        if not moved:
            # update in memory cache
            if not (putRequest.X, putRequest.Y) in self._inMemoryCache:
                self._inMemoryCache[(putRequest.X, putRequest.Y)] = set([])
            self._inMemoryCache[(putRequest.X, putRequest.Y)].add(putRequest.Object)
            
            self._db.execute("INSERT INTO game_board VALUES(?, ?, ?, ?)", 
                             (putRequest.X, putRequest.Y, objType, objId))
        
        
        self.raiseEvent(ChangeContentsEvent(putRequest.X, putRequest.Y,
                                            ChangeContentsEvent.INSERT,
                                                     putRequest.Object))   
        return self._requestAcknowledged(putRequest, True, ackType=PutResult)
        
    def removeObject(self, removeRequest):
        
        try:
            objType, objId = self._objectStore.getDatabasePointer(removeRequest.Object)
        except Exception as e:
            return self._requestFailed(removeRequest, e)
        
        c = self._db.execute("SELECT x, y FROM game_board WHERE objType=? AND objId=?",
                             (objType, objId))
        for row in c.fetchall(): # SHOULD BE AT MOST ONE. TODO, check?
            oldX, oldY = row
            
            # update the in memory cache
            if removeRequest.Object in self._inMemoryCache.get((oldX, oldY), set([])):
                self._inMemoryCache[(oldX, oldY)].remove(removeRequest.Object)
                
            self.raiseEvent(ChangeContentsEvent(oldX, oldY,
                                                ChangeContentsEvent.REMOVE,
                                                removeRequest.Object))
            break
        self._db.execute("DELETE FROM game_board WHERE objType=? AND objId=?",
                         (objType, objId))
        
        return self._requestAcknowledged(removeRequest, True, ackType=RemoveResult)
    
    def locateObject(self, locateRequest):
        try:
            objType, objId = self._objectStore.getDatabasePointer(locateRequest.Object)
        except Exception as e:
            # TODO: Only a not found execption should be acknowledged.
            return self._requestAcknowledged(locateRequest, None, ackType=LocateResult)
        
        c = self._db.execute("SELECT x,y FROM game_board WHERE objType=? AND objId=?", (objType, objId))
        lookupRow = c.fetchone()
        
        if lookupRow is None:
            return self._requestAcknowledged(locateRequest, None, ackType=LocateResult)
        
        x,y = lookupRow
        
        return self._requestAcknowledged(locateRequest, (x,y), ackType=LocateResult)