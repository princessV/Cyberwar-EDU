'''
Created on Feb 12, 2018

@author: seth_
'''
import unittest

from cyberwar.core.Board import Board, ContentsRequest
from cyberwar.core.ObjectStore import ObjectStore
from cyberwar.terrain.Loader import Loader as TerrainLoader
from cyberwar.terrain.Layer import Layer as TerrainLayer
from cyberwar.terrain.Layer import InitializeGameTerrainRequest
from cyberwar.terrain.initialization_algorithms import SimpleTerrainInitialization
from cyberwar.terrain.types import BaseType, Land, Water

import sqlite3

class Test_Layer(unittest.TestCase):


    def testBasic1(self):
        db = sqlite3.connect(":memory:")
        
        Board.NewBoard(db, 100, 100)
        
        TerrainLoader.InitializeDatabase(db)
        tLoader = TerrainLoader()
        
        store = ObjectStore(db)
        store.registerLoader(BaseType.ObjType(), tLoader)
        
        store.initialize()
        
        b = Board(db, store)
        terrain = TerrainLayer(b)
        
        initAlgorithm = SimpleTerrainInitialization(water=.6)
        initRequest = InitializeGameTerrainRequest("app", initAlgorithm)
        
        response = terrain.send(initRequest)
        self.assertTrue(response)
        
        sMap = ""
        for i in range(100):
            for j in range(100):
                contents = terrain.send(ContentsRequest("app", i, j))
                for obj  in contents.Value:
                    if isinstance(obj, Land):
                        sMap += "#"
                    elif isinstance(obj, Water):
                        sMap += "="
            sMap += "\n"
        print(sMap)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()