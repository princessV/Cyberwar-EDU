'''
Created on Feb 12, 2018

@author: seth_
'''

import random

from ..core.Board import DimensionsRequest, PutRequest, InitializeObjectRequest
from .types import Water, Land

class SimpleTerrainInitialization:
    def __init__(self, water=0.4):
        self._waterPercent = water
        
    def initialize(self, terrainLayer):
        sender = terrainLayer.LAYER_NAME
        
        result = terrainLayer.send(DimensionsRequest(sender))
        if not result: return result
        
        maxX, maxY = result.Value
        totalSquares = maxX * maxY
        
        waterSquares = self._waterPercent * totalSquares
        waterSquareCache = {}
        waterGenesisCount = random.randint(2, 5)
        if waterGenesisCount > 3:
            waterGenesisCount = waterGenesisCount * waterGenesisCount # 1, 2, 3, 16, 25
            
        borderSet = set([])
        while len(waterSquareCache) < waterGenesisCount and len(waterSquareCache) < waterSquares:
            randx = random.randint(0, maxX-1)
            randy = random.randint(0, maxY-1)
            waterSquareCache[(randx, randy)]=True
            borderSet.add((randx, randy))
        
        waterSquareCount = 0        
        while waterSquareCount < waterSquares:
            phaseBaseOdds = .1#random.randint(13,14)/100.0
            momentumOdds = random.randint(5, 50)/1000.0
            #print("Examining Border Set of size {}".format(len(borderSet)))
            nextBorderSet = set([])
            while borderSet:
                examine = borderSet.pop()
                #print("Examining border {}".format(examine))
                candidates = []
                nearCount = 0
                for xDelta, yDelta in [(xDelta, yDelta) for xDelta in [-1,0,1] for yDelta in [-1,0,1]]:
                    if (xDelta, yDelta) == examine: continue
                    dSquare = examine[0] + xDelta, examine[1] + yDelta
                    #print("\tLooking at delta {}".format(dSquare))
                    if waterSquareCache.get(dSquare,False) == True:
                        nearCount += 1
                        #print("\t\tWater! Nearcount now {}".format(nearCount))
                    else:#if dSquare not in waterSquareCache:
                        candidates.append(dSquare)
                        #print("\t\tNot yet examined. Adding to candidates.")
                odds = phaseBaseOdds + (momentumOdds * nearCount*nearCount) # ranges between 50% and 90%
                added = False
                for candidate in candidates:
                    if odds > 1.0 and candidate in waterSquareCache and waterSquareCache[candidate] == False:
                        # We previously cleared this one. It is suppoed to be land.
                        # but if we have high momentum, flip it to water.
                        waterSquareCache[candidate] = True
                        nextBorderSet.add(candidate)
                        waterSquareCount += 1
                        added = True
                    elif random.random() < odds:
                        waterSquareCache[candidate] = True
                        nextBorderSet.add(candidate)
                        waterSquareCount += 1
                        added = True
                        #odds = odds - 0.05
                    else:
                        waterSquareCache[candidate] = False
                if not added and candidates:
                    # We didn't even add one. Add a random candidate
                    random.shuffle(candidates)
                    waterSquareCache[candidates[0]] = True
                    waterSquareCount += 1
                    nextBorderSet.add(candidate)
            borderSet = nextBorderSet
            if not borderSet:
                #print("Brick wall. Quit")
                break
        #print("Water Square Count {}. Expected {}".format(waterSquareCount, waterSquares))
            
        for x in range(maxX):
            for y in range(maxY):
                if waterSquareCache.get((x,y), False):
                    squareType = Water()
                else:
                    squareType = Land()
                #self._objStore.addObjectToGame(squareType.ObjType(), squareType)
                r = terrainLayer.send(InitializeObjectRequest(sender,
                                                              squareType,
                                                              squareType.ObjType()))
                if not r: return r
                
                r = terrainLayer.send(PutRequest(sender, x, y, squareType))
                if not r: return r
        return True