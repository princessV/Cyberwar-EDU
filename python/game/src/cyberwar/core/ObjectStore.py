'''
Created on Feb 12, 2018

@author: seth_
'''

class ObjectStore:
    
    def __init__(self, db):
        self._db = db
        self._inMemoryObjects = {}
        self._inMemoryIdMap = {}
        self._loaders = {}
        self._nextId = 0
        self._loaded = False
        
    def registerLoader(self, objType, loader):
        if self._loaded:
            raise Exception("Cannot register loader after initialization")
        self._loaders[objType] = loader
        
    def initialize(self):
        if self._loaded: return
        for objType in self._loaders:
            loader = self._loaders[objType]
            c = self._db.execute("SELECT * FROM {}".format(loader.tableName()))
            for row in c.fetchall():
                objId = row[0]
                obj = loader.load(row)
                if not obj:
                    raise Exception("Loading of {} object {} failed.".format(objType, objId))
                
                self._inMemoryIdMap[objId] = obj
                self._inMemoryObjects[obj] = (objType, objId)
                
                self._nextId = max(self._nextId, objId)
        self._loaded = True
        
    def commit(self):
        for obj in self._inMemoryObjects:
            self.save(obj, dirtyOnly=True)
        self._db.commit()
                
    def load(self, objType, objId, reload=False):
        if not self._loaded:
            return Exception("Database not ready")
        
        if objId in self._inMemoryIdMap and not reload:
            # TODO: make sure obj type matches
            # TODO: Allow different id's per objtype?
            return self._inMemoryIdMap[objId]
        
        if objType not in self._loaders:
            raise Exception("Unknown type {} (no loader)".format(objType))
        loader = self._loaders[objType]
        c = self._db.execute("SELECT * FROM {} WHERE objId=?".format(loader.tableName()), objId)
        objData = c.fetchone()
        if not objData:
            raise Exception("No such object with ID {}".format(objId))
        obj = loader.load(objData)
        if not obj:
            raise Exception("Loading failed for obj with ID {}".format(objId))
        
        self._inMemoryIdMap[objId] = obj
        self._inMemoryObjects[obj] = (objType, objId)
        
        return obj
    
    def save(self, object, dirtyOnly=False):
        if not self._loaded:
            return Exception("Database not ready")
        
        if object not in self._inMemoryObjects:
            raise Exception("Object {} does not exist in database. Cannot save.".format(object))
        
        objType, objId = self._inMemoryObjects[object]
        if objType not in self._loaders:
            raise Exception("Unknown type {} (no loader)".format(objType))
        
        loader = self._loaders[objType]
        if dirtyOnly and not loader.isDirty(object):
            return
        objData = [objId] + loader.unload(object)
        template = ",".join(["?"]*len(objData))
        self._db.execute("REPLACE INTO {} VALUES({})".format(loader.tableName(),
                                                            template),
                   objData)
            
    def getDatabasePointer(self, object):
        if not self._loaded:
            return Exception("Database not ready")
        
        if object not in self._inMemoryObjects:
            raise Exception("Object {} does not exist in database. Cannot save.".format(object))
        
        objType, objId = self._inMemoryObjects[object]
        return objType, objId
    
    def hasObject(self, object):
        return (object in self._inMemoryObjects)
        
    def addObjectToGame(self, objType, object):
        if not self._loaded:
            return Exception("Database not ready")
        
        if objType not in self._loaders:
            raise Exception("Unknown type {} (no loader)".format(objType))
        
        self._nextId += 1
        objId = self._nextId
        self._inMemoryIdMap[objId] = object
        self._inMemoryObjects[object] = (objType, objId)
        
        self.save(object)
        
        return objId

    def removeObjectFromGame(self, obj):
        if not self._loaded:
            return Exception("Database not ready")
        
        if obj not in self._inMemoryObjects:
            raise Exception("Object {} does not exist in database. Cannot remove.".format(obj))
        
        objType, objId = self._inMemoryObjects[obj]
        if objType not in self._loaders:
            raise Exception("Unknown type {} (no loader)".format(objType))
        
        loader = self._loaders[objType]
        
        self._db.execute("DELETE FROM {} WHERE objId=?".format(loader.tableName()),
                         (objId,))
        del self._inMemoryIdMap[objId]
        del self._inMemoryObjects[obj]
    
    