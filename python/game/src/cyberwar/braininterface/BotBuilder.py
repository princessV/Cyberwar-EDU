'''
Created on Apr 4, 2018

@author: seth_
'''

from ..controlplane.objectdefinitions import ControlPlaneObjectAttribute, Tangible, Observer
from ..controlplane.objectdefinitions import ControlPlaneObject
from .Loader import BrainEnabled
import random

class BotBuilder(ControlPlaneObjectAttribute):
    
    def __init__(self):
        super().__init__("botbuilder")
        self._designs = {}
        self._brainMaker = None
        
        # use ID's rather than objects so that they can be reloaded
        self._builtBotIds = []
        
    def configureBrainMaker(self, brainMaker):
        self._brainMaker = brainMaker
        
    def loadDesign(self, designName, designSpec):
        self._designs[designName] = designSpec
        
    def buildBot(self, designName, name, address, brainZip):
        if not self._brainMaker:
            raise Exception("No brain maker")
        print("get design", designName)
        botAttributes = self._designs[designName]
        print("Got attributes",[str(a) for a in botAttributes])
        brainPath = self._brainMaker.initializeBrain(name, address, brainZip)
        print("Got brainPath", brainPath)
        brainIdentifier = random.randint(1,2**32)
        print("Got id", brainIdentifier)
        brainAttr = BrainEnabled(brainPath, brainIdentifier)
        bot = ControlPlaneObject(brainAttr, *botAttributes)
        self._builtBotIds.append(bot.numericIdentifier())
        return bot
    
    def builtBots(self):
        return self._builtBotIds
    
    #def releaseBot(self, bot):
    #    botId = bot.numericIdentifier()
    #    if botId in self._builtBotIds:
    #        self._builtBotIds.remove(botId)
        
    def rawData(self): return [("Bots Built", self._builtBotIds)]
    
    def __str__(self): return "BotBuilder"