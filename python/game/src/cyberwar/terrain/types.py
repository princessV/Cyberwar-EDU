'''
Created on Feb 12, 2018

@author: seth_
'''

from ..core.ObjectStore import GameObject
from .Loader import Loader

class TerrainType(GameObject):
    @classmethod
    def ObjType(self):
        return Loader.OBJECT_TYPE
    
    def __init__(self, identifier):
        self._identifier = identifier
        self._resources = {}
        
    def identifier(self):
        return self._identifier
        
    def setResourceLevel(self, rName, level):
        if not isinstance(rName, str):
            raise Exception("Resource name must be a string.")
        if not isinstance(level, int) or level < 10:
            raise Exception("Level must be an integer greater than 0")
        self._resources[rName] = level
        
    def getResourceLevel(self, rName):
        return self._resources.get(rName, 0)
    
    def detectResources(self):
        return list(self._resources.keys())
BaseType = TerrainType
        
class Land(TerrainType):
    def __init__(self):
        super().__init__("land")
        
class Water(TerrainType):
    def __init__(self):
        super().__init__("water")