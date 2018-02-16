

from playground.common.io.ui.CLIShell import CLIShell, AdvancedStdio

from .core.ObjectStore import ObjectStore
from .core.Board import Board, PutRequest

from .terrain.Loader import Loader as TerrainLoader
from .terrain.Layer import Layer as TerrainLayer
from .terrain.Layer import InitializeGameTerrainRequest
from .terrain.initialization_algorithms import SimpleTerrainInitialization

from .controlplane.Layer import Layer as ControlPlaneLayer
from .controlplane.objectdefinitions import Mobile, Observer, Tangible
from .controlplane.Directions import Directions

from .braininterface.Loader import Loader as BrainObjectLoader
from .braininterface.Layer import Layer as BrainControlLayer
from .braininterface.Layer import CreateBrainControlledObjectRequest

import sqlite3, asyncio


Command = CLIShell.CommandHandler
Loaders = [TerrainLoader, BrainObjectLoader]

def CreateGameObject(maxX, maxY, db):
    
    Board.NewBoard(db, maxX, maxY)
    for loader in Loaders:
        loader.InitializeDatabase(db)
    
    store = ObjectStore(db)
    store.registerLoader(BrainObjectLoader.OBJECT_TYPE, BrainObjectLoader())
    store.registerLoader(TerrainLoader.OBJECT_TYPE, TerrainLoader())
    store.initialize()
    
    game = BrainControlLayer(
        ControlPlaneLayer(
            TerrainLayer(
                Board(db, store))))
    
    initAlgorithm = SimpleTerrainInitialization(water=.6)
    initRequest = InitializeGameTerrainRequest("game", initAlgorithm)
    
    r = game.send(initRequest)
    if not r:
        raise Exception("Could not create terrain. {}".format(r.Value))
    return game

TestBrainDirectory = "/home/sethjn/WIN_DEV/stage/bot_brain/"

class GameConsole(CLIShell):
    def __init__(self, game):
        super().__init__(prompt=">> ")
        
        self.game = game
        
        demo1commandHandler = Command("demo1",
                                      "Run the first demo. Mostly debugging. Remove later",
                                      self._runDemo)
        self.registerCommand(demo1commandHandler)
        
    def _runDemo(self, writer):
        writer("Create Bot Brain, Connect to Bot\n")
        r = self.game.send(CreateBrainControlledObjectRequest("game",
                                                              TestBrainDirectory,
                                                              Mobile(Directions.N, 2),
                                                              Observer(5),
                                                              Tangible(100)
                                                              ))
        if not r:
            writer("Could not create object. {}\n\n".format(r.Value))
            return
        
        writer("Object Created.\n")
        newObject = r.Value    
            
        r = self.game.send(PutRequest("game", 1, 1, newObject))
        if not r:
            writer("Could not place object on board {}".format(r.Value))
            return
        
        writer("Object placed at 1 1\n")
        
    def start(self):
        loop = asyncio.get_event_loop()
        self.registerExitListener(lambda reason: loop.call_later(1.0, loop.stop))
        AdvancedStdio(self)
        
if __name__=="__main__":
    asyncio.get_event_loop().set_debug(True)
    import logging
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(logging.NOTSET)
    root.debug("Creating Game")
    db = sqlite3.connect(":memory:")
    game = CreateGameObject(10, 10, db)
    gameshellFactory = GameConsole(game)
    root.debug("Game Created. Startup shell.")
    asyncio.get_event_loop().call_soon(gameshellFactory.start)
    try:        
        asyncio.get_event_loop().run_forever()
    finally:
        print("Shutdown. Cleanup all game-related stuff.")
        game.cleanup()
    