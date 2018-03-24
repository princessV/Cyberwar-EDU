'''
Created on Feb 13, 2018

@author: seth_
'''

class Direction:
    def __init__(self, name, xDelta, yDelta):
        self._name = name
        self._xDelta = xDelta
        self._yDelta = yDelta
        
    def getSquare(self, currentSquare):
        return currentSquare[0] + self._xDelta, currentSquare[1] + self._yDelta
    
    def name(self):
        return self._name
    
    def __hash__(self):
        return hash((self._name, self._xDelta, self._yDelta))
    
    def __eq__(self, d):
        return isinstance(d, Direction) and d._xDelta == self._xDelta and d._yDelta == self._yDelta
    
    def __str__(self):
        return self.name()
    
class DirectionsContainer:
    def __init__(self):
        # bottom of board is 0,0, so higher numbers are north and east.
        self.N = Direction("north", 0, 1)
        self.NE = Direction("north-east", 1, 1)
        self.E = Direction("east", 1, 0)
        self.SE = Direction("south-east", 1, -1)
        self.S = Direction("south", 0, -1)
        self.SW = Direction("south-west", -1, -1)
        self.W = Direction("west", -1, 0)
        self.NW = Direction("north-west", -1, 1)
        
        self._allDirections = [self.N, self.NE,
                               self.E, self.SE,
                               self.S, self.SW,
                               self.W, self.NW]
        self._nameMapping = {}
        for d in self._allDirections:
            self._nameMapping[d.name()] = d
        
    def __getitem__(self, directionName):
        return self._nameMapping[directionName]
        
    def __str__(self):
        return self._name
    
    def __repr__(self):
        return "Direction {}".format(self._name)
        
    def __contains__(self, obj):
        return obj in self._allDirections
Directions = DirectionsContainer()