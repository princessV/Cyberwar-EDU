
from ..core.messages import Request
from ..core.Board import PutRequest, LocateRequest, ContentsRequest
from ..core.Layer import Layer as LayerBase

class InitializeGameTerrainRequest(Request):
    def __init__(self, sender, initializationAlgorithm):
        super().__init__(sender, TerrainLayer.LAYER_NAME, Algo=initializationAlgorithm)
        
# TODO: Add a resource changing request

class TerrainLayer(LayerBase):
    LAYER_NAME = "terrain"
    
    def __init__(self, lowerLayer):
        super().__init__(self.LAYER_NAME, lowerLayer)
        self._initialized = False
    
    def _handleRequest(self, req):
        if isinstance(req, InitializeGameTerrainRequest):
            if self._initialized:
                return self._requestFailed(req, "Gameboard Already Initialized")
            initialized = req.Algo.initialize(self)
            
            if initialized:
                return self._requestAcknowledged(req)
            else:
                # TODO, assert that this is a response type
                return initialized
        else:
            return self._requestFailed(req, "Unknown Request")
Layer = TerrainLayer