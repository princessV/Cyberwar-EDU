

from playground.common.io.ui.CLIShell import CLIShell, AdvancedStdio
from playground import Configure
from playground.network.devices.vnic.connect import NetworkManager

from .core.ObjectStore import ObjectStore
from .core.Layer import StartGameRequest
from .core.Board import Board, PutRequest, DimensionsRequest, ContentsRequest, ReleaseObjectRequest

from .terrain.Loader import Loader as TerrainLoader
from .terrain.Layer import Layer as TerrainLayer
from .terrain.Layer import InitializeGameTerrainRequest
from .terrain.types import Land, Water
from .terrain.initialization_algorithms import SimpleTerrainInitialization

from .controlplane.Layer import Layer as ControlPlaneLayer
from .controlplane.objectdefinitions import Mobile, Observer, Tangible, ControlPlaneObject
from .controlplane.Directions import Directions

from .braininterface.Loader import Loader as BrainObjectLoader
from .braininterface.Layer import Layer as BrainControlLayer
from .braininterface.Layer import CreateBrainControlledObjectRequest, GetBrainObjectByIdentifier

import sqlite3, asyncio, os, configparser, time, shutil

Command = CLIShell.CommandHandler
Loaders = [TerrainLoader, BrainObjectLoader]

AttributeConstructor = {
    
    "observer": lambda section: Observer(observationRange = section.getint("observer.observation_range")),
    "mobile"  : lambda section: Mobile(heading=Directions.N, 
                                       squaresPerSecond = section.getfloat("mobile.squares_per_second")),
    "tangible": lambda section: Tangible(hp = section.getint("tangible.hp"))
    }

BRAIN_REQUIRED_FILES = ["translations.py"]

game_pnetworking_template = """
[devices]
gameswitch = switch
gamevnic = vnic

[Config_gamevnic]
auto_enable = true
playground_address = {address}

[connections]
gamevnic = gameswitch

[routes]
__default__ = gamevnic

[Config_gameswitch]
auto_enable = true
physical_connection_type = remote
tcp_address = {switch_host}
tcp_port = {switch_port}
"""

brain_pnetworking_template = """
[devices]
brainswitch = switch
brainvnic = vnic

[Config_brainvnic]
auto_enable = true
playground_address = {address}

[connections]
brainvnic = brainswitch

[routes]
__default__ = brainvnic

[Config_brainswitch]
auto_enable = true
physical_connection_type = remote
tcp_address = {switch_host}
tcp_port = {switch_port}
"""

def InitPlayground(switchHost, switchPort, address, root=None):
    if root == None:
        root = os.getcwd()
        
    pdir = os.path.join(root, ".playground") 
    if not os.path.exists(pdir):
        os.mkdir(pdir)
        
    with open(os.path.join(pdir, "networking.ini"), "w+") as f:
        f.write(game_pnetworking_template.format(switch_host=switchHost,
                                                 switch_port=switchPort,
                                                 address=address))

def InitGamePaths(source=None, root=None):
    if root == None:
        root = Configure.CurrentPath()
    if source == None:
        source = os.getcwd()
        
    gamepath = os.path.join(Configure.CurrentPath(), "cyberwar_edu") # .playground/cyberwar_edu
    if not os.path.exists(gamepath):
        os.mkdir(gamepath)
    templatesPath = os.path.join(gamepath, "templates")
    if not os.path.exists(templatesPath):
        os.mkdir(templatesPath)
    brainTemplatesPath = os.path.join(templatesPath, "brains")
    if not os.path.exists(brainTemplatesPath):
        os.mkdir(brainTemplatesPath)
    brainsPath = os.path.join(gamepath, "brains")
    if not os.path.exists(brainsPath):
        os.mkdir(brainsPath)
        
    shutil.copy(os.path.join(source, "object_types.ini"),
                gamepath)
    for fileName in os.listdir(source):
        if fileName.endswith("_brain.py"):
            shutil.copy(os.path.join(source, fileName), brainTemplatesPath)
            
    for fileName in BRAIN_REQUIRED_FILES:
        shutil.copy(os.path.join(source, fileName), brainTemplatesPath)

class GameConsole(CLIShell):
    
    def __init__(self):
        super().__init__(prompt=">> ")
        
        self._db = None
        self._game = None
        self._gameGenerating = False
        self._deviceManager = NetworkManager()
        self._deviceManager.loadConfiguration()
        
        self._DefinedTypes = {}
        self._objIdToBrain = {}
        
        newgameCommandHandler = Command("newgame",
                                        "Create a new game (erase any existing game data!)",
                                        self._newGameCommand)
        createobjCommandHandler = Command("createobj",
                                          "Create a new player object. Specify x,y, type, brain_type",
                                          self._newPlayerObjectCommand)
        printmapCommandHandler = Command("printmap",
                                         "Print a text map of the whole board",
                                         self._printMapCommand)
        destroyCommandHandler  = Command("destroyobj",
                                         "Destroy a player object on the map by identifier",
                                         self._destroyObjectCommand)
        self.registerCommand(newgameCommandHandler)
        self.registerCommand(createobjCommandHandler)
        self.registerCommand(printmapCommandHandler)
        self.registerCommand(destroyCommandHandler)
        self._reloadConfiguration()
        
    def _reloadConfiguration(self):
        if self._gameGenerating:
            raise Exception("Cannot reload config until game generation is complete")
        self._gamepath = os.path.join(Configure.CurrentPath(), "cyberwar_edu") # .playground/cyberwar_edu
        self._objectTypesFile = os.path.join(self._gamepath, "object_types.ini")
        self._templatesPath = os.path.join(self._gamepath, "templates")
        self._brainTemplatesPath = os.path.join(self._templatesPath, "brains")
        self._brainsPath = os.path.join(self._gamepath, "brains")
        self._dbFile = os.path.join(self._gamepath, "board.db")
        loadGame = os.path.exists(self._dbFile)
        self._db = sqlite3.connect(self._dbFile, isolation_level=None)
        self._objectStore = None
        #self._db.execute("PRAGMA synchronous = OFF")
        #self._db.execute("PRAGMA journal_mode = OFF")
        if loadGame:
            try:
                self._loadGame()
            except Exception as e:
                print("Could not load game", e)
                self._game = None
        
        not os.path.exists(self._gamepath) and os.mkdir(self._gamepath)
        not os.path.exists(self._templatesPath) and os.mkdir(self._templatesPath)
        not os.path.exists(self._brainTemplatesPath) and os.mkdir(self._brainTemplatesPath)
        not os.path.exists(self._brainsPath) and os.mkdir(self._brainsPath)
        
        self._playerObjectTypes = configparser.ConfigParser()
        if os.path.exists(self._objectTypesFile):
            self._playerObjectTypes.read(self._objectTypesFile)
            
        self._initialObjects = configparser.ConfigParser()
        
    def saveGame(self):
        # Two stage save. First, we commit objects to the dabase
        self._objectStore and self._objectStore.commit()
        # then we commit the database to file
        self._db and self._db.commit()
        
    def autosave(self):
        self.saveGame()
        asyncio.get_event_loop().call_later(30.0, self.autosave)
        
    def _loadGame(self):
        if self._gameGenerating:
            raise Exception("Cannot reload config until game generation is complete")
        for loader in Loaders:
            loader.InitializeDatabase(self._db)
            
        store = ObjectStore(self._db)
        store.registerLoader(BrainObjectLoader.OBJECT_TYPE, BrainObjectLoader())
        store.registerLoader(TerrainLoader.OBJECT_TYPE, TerrainLoader())
        store.initialize()
        self._objectStore = store
        
        self._game = BrainControlLayer(
                ControlPlaneLayer(
                    TerrainLayer(
                        Board(self._db, store))))
        
        self._game.send(StartGameRequest("game"))

        
    def _newGame(self, maxX, maxY):
        if self._gameGenerating:
            raise Exception("Cannot reload config until game generation is complete")
        if os.path.exists(self._dbFile):
            print("Deleting old database")
            self._db.close()
            os.unlink(self._dbFile)
            print("Still exists?",os.path.exists(self._dbFile))
            self._db = sqlite3.connect(self._dbFile)
        Board.NewBoard(self._db, maxX, maxY)
        
        self._loadGame()
        
        initAlgorithm = SimpleTerrainInitialization(water=.6)
        initRequest = InitializeGameTerrainRequest("game", initAlgorithm)
        
        start = time.time()
        r = self._game.send(initRequest)
        if not r:
            raise Exception(r.Value)
        end = time.time()
        print("init in {} seconds".format(end-start))
        """
        
        coro = asyncio.get_event_loop().run_in_executor(None, self._game.send, initRequest)
        f = asyncio.ensure_future(coro)
        f.add_done_callback(self._newGameReady)
        self._gameGenerating = True
        
    def _newGameReady(self, result):
        self._gameGenerating = False
        r = result.result()
        if not r:
            # don't have a 'writer' fall back to transport
            self.transport.write("Could not create terrain. {}".format(r.Value))
            return
        self._
 = True
        self.transport.write("Game loaded")"""
        
        
    def _getObjectTypeAttributes(self, objectType):
        if objectType not in self._playerObjectTypes:
            raise Exception("No such type {}".format(objectType))
        typeSection = self._playerObjectTypes[objectType]
        attributes = []
        if "attributes" in typeSection:
            try:
                attributes = [AttributeConstructor[attrName](typeSection) for attrName in typeSection["attributes"].split("\n")]
            except Exception as e:
                raise Exception("Misconfigured type. {}".format(e))
        
        return attributes
    
    def _getBrain(self, brainType, **kargs):
        brainFileName = "{}.py".format(brainType)
        brainFQFileName = os.path.join(self._brainTemplatesPath, brainFileName)
        print(brainFQFileName)
        if not os.path.exists(brainFQFileName):
            raise Exception("No Such Brain {}".format(brainType))
        with open(brainFQFileName, "r") as f:
            code = ""
            templateLine = False
            for line in f.readlines():
                if line.strip().startswith("#%") and "TEMPLATE-ON" in line:
                    templateLine = True
                elif line.strip().startswith("#%") and "TEMPLATE-OFF" in line:
                    templateLine = False
                elif templateLine:
                    code += line.format(**kargs)
                else:
                    code += line
            return code
        
    def _initializeBrain(self, brainPath, brainType, **kargs):
        brainCode = self._getBrain(brainType, **kargs)
        print("got brainCode")
        if os.path.exists(brainPath):
            raise Exception("Path already exists")
        os.mkdir(brainPath)
        
        for requiredFile in BRAIN_REQUIRED_FILES:
            requiredFQFile = os.path.join(self._brainTemplatesPath, requiredFile)
            if not os.path.exists(requiredFQFile):
                raise Exception("Invalid installation. File {} not present.".format(requiredFile))
            shutil.copy(requiredFQFile, brainPath)
        with open(os.path.join(brainPath, "brain.py"), "w+") as f:
            f.write(brainCode)
        ppath = os.path.join(brainPath, ".playground")
        os.mkdir(ppath)
        
        kargs["switch_host"], kargs["switch_port"] = self._deviceManager.getDevice("gameswitch").tcpLocation()
        with open(os.path.join(ppath, "networking.ini"), "w+") as f:
            f.write(brain_pnetworking_template.format(**kargs))
        os.mkdir(os.path.join(ppath, "connectors"))
    
    def _createPlayerObject(self, startX, startY, objectType, brainType, *kargsList):
        kargs = {}
        for argpair in kargsList:
            print(argpair)
            try:
                k,v = argpair.split("=")
                kargs[k] = v
            except Exception as e:
                raise Exception("Cannot create object. Requires a list of k=v pairs to brain template. Error={}".format(e))
        brainPath = os.path.join(self._brainsPath, str(time.time()))
        print("brain path", brainPath)
        self._initializeBrain(brainPath, brainType, **kargs)
        
        print("get attributes")
        attributes = self._getObjectTypeAttributes(objectType)
        print("got", attributes)
        r = self._game.send(CreateBrainControlledObjectRequest("game",
                                                              brainPath,
                                                              *attributes
                                                              ))
        if not r:
            raise Exception(r.Value)
        newObject = r.Value
        #self._objIdToBrain[newObject.numericIdentifier()] = brainPath
            
        r = self._game.send(PutRequest("game", startX, startY, newObject))
        if not r:
            raise Exception(r.Value)
        
    def _newPlayerObjectCommand(self, writer, x, y, objectType, brainType, *brainArgs):
        if not self._game:
            writer("Cannot create object until game starts.\n\n")
            return
        x,y = int(x), int(y)
        try:
            self._createPlayerObject(x, y, objectType, brainType, *brainArgs)
            writer("{} object created at {}\n\n.".format(objectType, (x,y)))
        except Exception as e:
            writer("{} could not be created. {}\n\n".format(objectType, e))
            
    """def _resetBrainCommand(self, writer, objectId, brainType, *brainArgs):
        objectId = int(objectId)
        if not objectId in self._objIdToBrain:
            writer("No such object with ID {}\n\n".format(objectId))
            return
        if not os.path.exists(self._objIdToBrain[objectId]):
            writer("No brain exists for ID {} anymore\n\n".format(objectId))
            return"""
        
    def _newGameCommand(self, writer, x, y):
        x, y = int(x), int(y)
        if self._game:
            yesno = input("WARNING: This will over-write the current game! Are you sure [y/N]? ")
            if yesno.lower().strip()[0] != 'y':
                writer("New game operation cancelled.\n\n")
                return
            self._game.cleanup()
        try:
            self._newGame(x, y)
            writer("Game created.\n\n")
        except Exception as e:
            writer("Could not create new game. {}\n\n".format(e))
            
    def _printMapCommand(self, writer):
        if not self._game:
            writer("No map. Game not started.\n\n")
            return
        dimensionsResult = self._game.send(DimensionsRequest("game"))
        maxX,maxY = dimensionsResult.Value
        s = ""
        line = ""
        for y in range(0, maxY):
            for x in range(0, maxX):
                contentsResult = self._game.send(ContentsRequest("game", x, y))
                contents = contentsResult.Value
                symbol = "X"
                terrainType = None
                otherObj = None
                for obj in contents:
                    if isinstance(obj, Land): terrainType=Land
                    elif isinstance(obj, Water): terrainType=Water
                    elif isinstance(obj, ControlPlaneObject): otherObj=obj
                if otherObj is not None:
                    symbol = "O"
                elif terrainType == Land:
                    symbol = "#"
                elif terrainType == Water:
                    symbol = "="
                line += symbol
            s = line + "\n" + s
            line = ""
        writer(s+"\n")
        
    def _destroyObjectCommand(self, writer, objId):
        objResult = self._game.send(GetBrainObjectByIdentifier("game", int(objId)))
        if not objResult:
            writer("Could not find object with id {}\n\n".format(objId))
            return
        releaseResult = self._game.send(ReleaseObjectRequest("game", objResult.Value))
        if not releaseResult:
            writer("Could not release object. Reason {}\n\n".format(releaseResult.Value))
            return
        writer("Object destroyed\n\n")
        
        
    def start(self):
        loop = asyncio.get_event_loop()
        self.registerExitListener(lambda reason: loop.call_later(1.0, loop.stop))
        AdvancedStdio(self)
        
    def stop(self):
        try:
            print("calling save")
            self.saveGame()
            print("save done")
        except Exception as e:
            print("had exception", e)
            pass
        if self._game:
            print("game cleanup")
            self._game.cleanup()
        
def main():
    
    import sys
    
    kargs = {}
    args = []
    
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                k,v = arg.split("=")
            else:
                k,v = arg,True
            kargs[k]=v
        elif arg.startswith("-"):
            kargs[k]=True
        else:
            args.append(arg)
            
    if "--init" in kargs:
        switchHost, switchPort, address = kargs["--init"].split(",")
        switchPort = int(switchPort)
        InitPlayground(switchHost, switchPort, address)
        expectedPlayground = os.path.join(os.getcwd(), ".playground")
        if Configure.CurrentPath() != expectedPlayground:
            raise Exception("Init didn't work")
        InitGamePaths()
        return
    
    if "--pypy" in kargs:
        from cyberwar.braininterface.Loader import Loader
        Loader.PYPY_PATH = os.path.expanduser(kargs["--pypy"])
    else:
        raise Exception("--pypy argument is required.")
        
    
    #asyncio.get_event_loop().set_debug(True)
    import logging
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(logging.NOTSET)
    root.debug("Creating Game")

    gameshell = GameConsole()
    asyncio.get_event_loop().call_soon(gameshell.start)
    try:        
        asyncio.get_event_loop().run_forever()
    finally:
        print("Shutdown. Cleanup all game-related stuff.")
        gameshell.stop()
        
if __name__=="__main__":
    main()
    