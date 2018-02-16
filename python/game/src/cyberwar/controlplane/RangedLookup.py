'''
Created on Feb 14, 2018

@author: seth_
'''

from .objectdefinitions import Observer

class RangedLookup:
    @classmethod
    def InRange(cls, location1, location2, range):
        x1, y1 = location1
        x2, y2 = location2
        return ((abs(x1-x2)+abs(y1-y2)) < range)
    
    def __init__(self):
        self._rangeLookups = {}
        self._reverseLookup = {}
    
    def observe(self, observer, location):
        try:
            x,y = location
        except:
            raise Exception("Ranged Lookup can only set on (x,y) values")
        observerAttr = observer.getAttribute(Observer)
        observerRange = observerAttr.range()
        
        # create a lookup "bucket"
        lookupCoordinateRange = int(x/observerRange), int(y/observerRange)
        
        if not observerRange in self._rangeLookups:
            self._rangeLookups[observerRange] = {}
        if not lookupCoordinateRange in self._rangeLookups[observerRange]:
            self._rangeLookups[observerRange][lookupCoordinateRange] = set([])
        self._rangeLookups[observerRange][lookupCoordinateRange].add(observer)
        self._reverseLookup[observer] = (x,y)
        
    def stopObserving(self, observer, location):
        try:
            x,y = location
        except:
            raise Exception("Ranged Lookup can only set on (x,y) values")
        observerAttr = observer.getAttribute(Observer)
        observerRange = observerAttr.range()
        
        # create a lookup "bucket"
        lookupCoordinateRange = int(x/observerRange), int(y/observerRange)
        
        if observerRange in self._rangeLookups: 
            if lookupCoordinateRange in self._rangeLookups[observerRange]:
                if observer in self._rangeLookups[observerRange][lookupCoordinateRange]:
                    self._rangeLookups[observerRange][lookupCoordinateRange].remove(observer)
                if len(self._rangeLookups[observerRange][lookupCoordinateRange]) == 0:
                    del self._rangeLookups[observerRange][lookupCoordinateRange]
            if len(self._rangeLookups[observerRange]) == 0:
                del self._rangeLookups[observerRange]
        if observer in self._reverseLookup:
            del self._reverseLookup[observer]
                    
    def getObserversInRange(self, location):
        observers = set([])
        try:
            x,y = location
        except:
            raise Exception("Ranged Lookup can only set on (x,y) values")
        for observationRange in self._rangeLookups:
            bucket = int(x/observationRange), int(y/observationRange)
            
            # Must do 9 lookups per bucket.
            for i in [-1, 0, 1]:
                for j in [-1, 0, 1]:
                    # might not be in range. This lookup is a square, but
                    # actual range is a star (manhattan distance)
                    lookupBucket = bucket[0]+i, bucket[1]+j
                    for observer in self._rangeLookups[observationRange].get(lookupBucket, set([])):
                        observerLocation = self._reverseLookup[observer]
                        if self.InRange(observerLocation, location, observationRange):
                            observers.add(observer)
                                        
        return observers
    
    def getLocation(self, observer):
        return self._reverseLookup.get(observer, None)