'''
Created on Feb 12, 2018

@author: seth_
'''

from ..core.PickleLoader import PickleLoader

class TerrainLoader(PickleLoader):
    OBJECT_TYPE = "game_terrain_object"
    @classmethod
    def TableName(cls):
        return "cyberwar_terrain_loader"
    
    def isDirty(self, object):
        return False
    
Loader = TerrainLoader