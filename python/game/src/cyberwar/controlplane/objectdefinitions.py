'''
Created on Feb 13, 2018

@author: seth_
'''

from .Directions import Directions

class ControlPlaneObject:
    OBJECT_ID = 0 # LOADERS MUST RELOAD THIS VALUE!!!
    
    OBJECT_LOOKUP = {} # LOADERS MUST ALSO RELOAD THIS VALUE !!!
    
    def __init__(self, *attributes):
        self._attributes = {}
        ControlPlaneObject.OBJECT_ID += 1
        self._numericId = ControlPlaneObject.OBJECT_ID
        self._identifier = "game_object_{}".format(self._numericId)
        for attribute in attributes:
            attributeClass = attribute.__class__
            
            if attributeClass in self._attributes:
                raise Exception("Duplicate attribute class {}".format(attributeClass))
            
            attributeParents = list(attributeClass.__mro__[1:])
            endIndex = attributeParents.index(ControlPlaneObjectAttribute)
            if endIndex == -1:
                raise Exception("Attribute {} does not descend from ControlPlanelObjecAttribute".format(attribute))
            attributeParents = attributeParents[:endIndex]
            
            self._attributes[attributeClass] = attribute
            for parent in attributeParents:
                if parent in self._attributes:
                    raise Exception("Duplicate attribute (inherited) class {}".format(parent))
                self._attributes[attributeClass] = parent
        for attribute in attributes:
            attribute.initializeObject(self)
    
    def numericIdentifier(self):
        return self._numericId
    
    def identifier(self):
        return self._identifier
    
    def getAttribute(self, attributeClass):
        for aClass in attributeClass.__mro__:
            if aClass == ControlPlaneObjectAttribute:
                # We've hit the abstract attr in the tree. We're done.
                break
            if aClass in self._attributes:
                return self._attributes[aClass]
        return None
    
    def getAttributes(self):
        return set(self._attributes.values())

class ControlPlaneObjectAttribute:
    REQUIRED = []
    OPTIONAL = []
    
    def __init__(self, identifier):
        self._coattributes = {}
        self._identifier = identifier
        
    def identifier(self):
        return self._identifier
    
    def initializeObject(self, object):
        for requiredClass in self.REQUIRED:
            coAttr = object.getAttribute(requiredClass)
            if coAttr is None:
                raise Exception("Invalid object definition. Attribute requires {}".format(requiredClass))
            self._coattributes[requiredClass] = coAttr
            
        for optionalClass in self.OPTIONAL:
            self._coattributes[optionalClass] = object.getAttribute(optionalClass)
            
    def getCoattribute(self, attributeClass):
        return self._coattributes.get(attributeClass, None)
    
    def rawData(self):
        return []
    
    def __str__(self):
        return self._identifier
    
class NamedObject(ControlPlaneObjectAttribute):
    def __init__(self, name):
        super().__init__("named")
        self._name = name
        
    def name(self): return self._name
    
    def rawData(self):
        return [("name", self._name)]
    
    def __str__(self):
        return "Named({})".format(self._name)

class Tangible(ControlPlaneObjectAttribute):
    def __init__(self, hp):
        super().__init__("tangible")
        self._maxHitpoints = hp
        self._hitpoints = hp
        
    def maxHitpoints(self): return self._maxHitpoints
    def hitpoints(self): return self._hitpoints
        
    def takeDamage(self, hp):
        self._hitpoints = max(0, self._hitpoints - hp)
        
    def repair(self, hp):
        self._hitpoints = min(self._maxHitpoints, self._hitpoints + hp) 
        
    def destroyed(self):
        return self._hitpoints == 0
    
    def health(self):
        if self._maxHitpoints == 0: return 0 # if you start with 0, you're always damaged
        return int((self._hitpoints/float(self._maxHitpoints))*100)
    
    def rawData(self):
        return [("hitpoints",self._hitpoints), ("max_hitpoints",self._maxHitpoints)]
    
    def __str__(self):
        return "Tangible({}/{})".format(self._hitpoints, self._maxHitpoints)
        
class Mobile(ControlPlaneObjectAttribute):
    REQUIRED = [Tangible]
    
    def __init__(self, heading, squaresPerSecond, waterAble=0):
        super().__init__("mobile")
        if heading not in Directions:
            raise Exception("{} is not a valid heading (direction).".format(heading))
        self._heading = heading
        self._squaresPerSecond = squaresPerSecond
        
    def heading(self): return self._heading

    def waterAble(self): return self._waterAble

    def squaresPerSecond(self):
        healthPercent = self.getCoattribute(Tangible).health()
        return self._squaresPerSecond * (healthPercent/100.0)
    
    def rawData(self):
        return [("heading", self._heading), ("speed",self.squaresPerSecond())]
    
    def __str__(self):
        return "Mobile({}, {} squares/sec)".format(self._heading, self._squaresPerSecond)
        
class Observer(ControlPlaneObjectAttribute):
    
    def __init__(self, observationRange):
        super().__init__("observer")
        self._range = observationRange
    
    def range(self): return self._range
    
    def view(self, observerLocation, objectLocation, object):
        # TODO: return the object as is for now.
        # Future versions could return a proxy object
        # limiting what can be seen about a given target object
        # No need to check range. That has been done for us.
        return object
    
    def rawData(self):
        return [("observation_range", self._range)]
    
    def __str__(self):
        return "Observer({})".format(self._range)