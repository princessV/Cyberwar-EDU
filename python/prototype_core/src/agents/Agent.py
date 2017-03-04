'''
Created on Feb 4, 2017

@author: sethjn
'''

#class AgentSpecification(object):


import GameDatabase

GameDatabase.RequiredTable("AGENT_TYPE", spec={"GUID":int,
                                                "metaType":str,
                                                "typeName":str})
GameDatabase.RequiredTable("AGENT_TYPE_PROPERTIES", spec={"typeGUID":int,
                                                          "propertyName":str,
                                                          "propertyData":str})
GameDatabase.RequiredTable("AGENTS", spec={"GUID":int,
                                           "typeGUID":int,
                                           "agentName":int,
                                           "hitpoints":int,
                                           "locationX":int,
                                           "LocationY":int})
GameDatabase.RequiredTable("AGENT_INVENTORY", spec={"agentGUID":int,
                                                    "inventoryItemGUID":int,
                                                    "quantity":int})

@GameDatabase.UniqueRowMap(table="AGENT_TYPE", uniqueKey="GUID")
@GameDatabase.QueryView(table="AGENT_TYPE_PROPERTIES", SELECT("propertyName","propertyData").WHERE("typeGUID=%(GUID)s"), loadinto="raw_properties")
class AgentBaseType(object):
    def onload(self):
        for pName, pData in self.raw_properties:
            if pName == "hitpoints": self.hitpoints = int(pData)
            elif pName == "sensorRange": self.sensorRange = int(pData)
            elif pName == "sensorRating": self.sensorRating = int(pData)
            elif pName == "visibilityRating": self.visibilityRating = int(pData)
        
    def newAgent(self, name, x, y):
        return Agent.DbCreate(typeGUID=self.GUID, agentName=name, 
                              hitpoints=self.hitpoints, locationX=x, locationY=y)

@GameDatabase.UniqueRowMap(table="AGENTS", uniqueKey="GUID")
@GameDatabase.QueryView(table="AGENT_INVENTORY", SELECT("inventoryItemGUID","quantity").WHERE("agentGUID=%(GUID)"), loadinto="inventory")
class Agent(object):
    def onLoad(self):
        self.agentType = AgentBaseType.DbLoad(self.typeGUID)
    
    def hitPoints(self):
        return self.hitpoints
    
    def location(self):
        return (self.locationX, self.locationY)
    
    def look(self):
        # todo, add terrain look
        maxX = self.locationX + self.agentType.sensorRange
        maxY = self.locationX + self.agentType.sensorRange
        
        minX = self.locationX - self.agentType.sensorRange
        minY = self.locationX - self.agentType.sensorRange
        
        cursor = self.db.tables.AGENTS.SELECT("GUID").WHERE('x > %s and x < %s and y > %s and y < %s' % (minX, maxX, minY, maxY))
        
        agents = []
        for i in cursor:
            agents.append(Agent.DbLoad(i.GUID))
        return agents
           
    def inventory(self):
        return []
    
    