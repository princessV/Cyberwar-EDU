'''
Created on Feb 14, 2018

@author: seth_
'''
import unittest

from cyberwar.core.Layer import Layer as BaseLayer
from cyberwar.core.Layer import StartGameRequest
from cyberwar.core.Board import Board, InitializeObjectRequest, PutRequest, ContentsRequest
from cyberwar.core.Board import ChangeContentsEvent
from cyberwar.core.ObjectStore import ObjectStore
from cyberwar.core.PickleLoader import PickleLoader
from cyberwar.terrain.Loader import Loader as TerrainLoader
from cyberwar.terrain.Layer import Layer as TerrainLayer
from cyberwar.terrain.Layer import InitializeGameTerrainRequest
from cyberwar.terrain.initialization_algorithms import SimpleTerrainInitialization
from cyberwar.terrain.types import BaseType, Land, Water

from cyberwar.controlplane.Layer import Layer as ControlPlaneLayer
from cyberwar.controlplane.Layer import ObjectScanRequest, ObjectMoveRequest
from cyberwar.controlplane.Layer import ObjectMoveCompleteEvent
from cyberwar.controlplane.objectdefinitions import ControlPlaneObject
from cyberwar.controlplane.objectdefinitions import Tangible, Mobile, Observer
from cyberwar.controlplane.Directions import Directions

import asyncio

import sqlite3

class FalseTimerLoop(asyncio.AbstractEventLoop):
    def __init__(self):
        self._clock = 0
        self._events = []
    def call_later(self, delay, event, *args):
        self._events.append(((self._clock+delay), event, args))
    def advanceClock(self, t):
        advanceTime = self._clock + t
        while self._events:
            if self._events[0][0] > advanceTime:
                break
            self._clock, event, args = self._events.pop(0)
            event(*args)
        self._clock = advanceTime
            

class ObjectLoader(PickleLoader):
    @classmethod
    def TableName(cls): return "game_objects"
    
    @classmethod
    def ObjectType(cls): return "game_object"
    
class GameController(BaseLayer):
    def __init__(self, lowerLayer):
        super().__init__("game_controller", lowerLayer)
        self.events = []
    def _handleEvent(self, event):
        self.events.append(event)
    def clearEvents(self):
        self.events = []

asyncio.set_event_loop(FalseTimerLoop())

class Test_ControlPlaneLayer(unittest.TestCase):
    
    def printMiniMap(self, scanResult, objsList):
        lastY = None
        s = ""
        line = ""
        for coord, contents in scanResult.Value:
            x, y =coord
            if y != lastY:
                s = line + "\n" + s # prepend the line. Y increases toward north 
                line = ""
                lastY = y
            symbol = "X"
            terrainType = None
            otherObj = None
            for obj in contents:
                if isinstance(obj, Land): terrainType=Land
                elif isinstance(obj, Water): terrainType=Water
                elif isinstance(obj, ControlPlaneObject): otherObj=obj
            if terrainType == Land:
                symbol = "#"
            elif terrainType == Water:
                symbol = "="
            if otherObj in objsList:
                index = objsList.index(otherObj)
                if index == -1: symbol = "o"
                elif index > 9: symbol = "O"
                else: symbol = str(index)
            elif otherObj is not None:
                symbol = "?"
            line += symbol
        s = line + "\n" + s
        print(s)

    def setUp(self):
        db = sqlite3.connect(":memory:")
        
        Board.NewBoard(db, 100, 100)
        
        TerrainLoader.InitializeDatabase(db)
        ObjectLoader.InitializeDatabase(db)
        
        tLoader = TerrainLoader()
        objLoader = ObjectLoader()
        
        store = ObjectStore(db)
        store.registerLoader(BaseType.ObjType(), tLoader)
        store.registerLoader(ObjectLoader.ObjectType(), objLoader)
        store.initialize()
        
        self._game = GameController(
            ControlPlaneLayer(
                TerrainLayer(
                    Board(db, store))))
        
        initAlgorithm = SimpleTerrainInitialization(water=.6)
        initRequest = InitializeGameTerrainRequest("app", initAlgorithm)
        
        response = self._game.send(initRequest)
        self.assertTrue(response)
        self._game.clearEvents()
        
        self.db = db
        self.store = store

    def tearDown(self):
        pass


    def testBasic1(self):
        # create two control objects
        obj1 = ControlPlaneObject(Tangible(hp=100),
                                  Mobile(heading=Directions.N,
                                         squaresPerSecond=.5),
                                  Observer(observationRange=7))
        
        obj2 = ControlPlaneObject(Tangible(hp=50),
                                  Mobile(heading=Directions.E,
                                         squaresPerSecond=1),
                                  Observer(observationRange=5))
        
        r = self._game.send(InitializeObjectRequest("app", obj1, ObjectLoader.ObjectType()))
        self.assertTrue(r)
        
        r = self._game.send(InitializeObjectRequest("app", obj2, ObjectLoader.ObjectType()))
        self.assertTrue(r)
        
        r = self._game.send(PutRequest("app", 25, 25, obj1))
        self.assertTrue(r)
        self.assertTrue(len(self._game.events)>0)
        self.assertTrue(isinstance(self._game.events[-1], ChangeContentsEvent))
        event = self._game.events.pop(-1)
        self.assertTrue(event.Object==obj1)
        self.assertTrue(event.X==25)
        self.assertTrue(event.Y==25)
        self._game.clearEvents()
        
        r = self._game.send(PutRequest("app", 26, 26, obj2))
        self.assertTrue(r)
        self.assertTrue(len(self._game.events)>0)
        self.assertTrue(isinstance(self._game.events[-1], ChangeContentsEvent))
        event = self._game.events.pop(-1)
        self.assertTrue(event.Object==obj2)
        self.assertTrue(event.X==26)
        self.assertTrue(event.Y==26)
        self._game.clearEvents()
        
        r = self._game.send(ObjectScanRequest("app", obj1))
        self.assertTrue(r)
        self.printMiniMap(r, [obj1, obj2])
        
        # use "game_controller" so that events go to the right place.
        r = self._game.send(ObjectMoveRequest("game_controller", obj1, Directions.E))
        self.assertTrue(r)
        
        r = self._game.send(ContentsRequest("app", 25, 25))
        self.assertTrue(r)
        self.assertTrue(obj1 in r.Value)
        
        asyncio.get_event_loop().advanceClock(1.0)
        
        # obj1 moves at .5 squares per second. Should not have moved yet
        r = self._game.send(ContentsRequest("app", 25, 25))
        self.assertTrue(r)
        self.assertTrue(obj1 in r.Value)
        
        asyncio.get_event_loop().advanceClock(1.0)
        
        # obj1 moves at .5 squares per second. Should have just moved
        self.assertTrue(len(self._game.events)>0)
        self.assertTrue(isinstance(self._game.events[-1], ObjectMoveCompleteEvent))
        event = self._game.events.pop(-1)
        print("Event message: ", event.Message)
        
        r = self._game.send(ContentsRequest("app", 25, 25))
        self.assertTrue(r)
        self.assertTrue(obj1 not in r.Value)
        
        self._game.clearEvents()
        
        r = self._game.send(ObjectScanRequest("app", obj1))
        self.assertTrue(r)
        self.printMiniMap(r, [obj1, obj2])
        
        r = self._game.send(ObjectMoveRequest("game_controller", obj1, Directions.N))
        self.assertTrue(r)
        
        asyncio.get_event_loop().advanceClock(2.0)
        self.assertTrue(len(self._game.events)>0)
        self.assertTrue(isinstance(self._game.events[-1], ObjectMoveCompleteEvent))
        event = self._game.events.pop(-1)
        print("Event message: ", event.Message)
        
        r = self._game.send(ObjectScanRequest("app", obj1))
        self.assertTrue(r)
        self.printMiniMap(r, [obj1, obj2])
        print("obj1 health: ", obj1.getAttribute(Tangible).health())
        print("obj2 health: ", obj2.getAttribute(Tangible).health())
        
        game2 = GameController(
            ControlPlaneLayer(
                TerrainLayer(
                    Board(self.db, self.store))))
        game2.send(StartGameRequest("app"))
        
        r = game2.send(ContentsRequest("app", 26, 26))
        self.assertTrue(r)
        for object in r.Value:
            if isinstance(object, ControlPlaneObject):
                obj2_new = object
                print(obj2_new, obj2_new.getAttributes())
                break
        r = game2.send(ObjectScanRequest("app", obj2_new))
        self.assertTrue(r)
        self.printMiniMap(r, [])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()