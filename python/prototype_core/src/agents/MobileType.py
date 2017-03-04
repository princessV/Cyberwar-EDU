'''
Created on Feb 4, 2017

@author: sethjn
'''

from Agent import AgentBaseType

GameDatabase.RequiredTable("LAST_MOVEMENT", spec={"agentGUID":int,
                                                "timestamp":float})

@GameDatabase.QueryUniqueView(table="LAST_MOVEMENT", uniqueKey="agentGUID", loadinto="timestamp")
class MobileType(AgentBaseType):
    def onLoad(self):
        AgentBaseType.onload(self)
        self.mobility = {}
        for pName, pData in self.raw_properties:
            # terrible hack. What's better?
            if pName == "MOBILITY":
                mobilityString = pData
                mobilityData = pData.split(",")
                for mobilityInfo in mobilityData:
                    mobilityType, mobilityDelay = mobilityInfo.split(":")
                    self.mobility[mobilityType] = mobilityDelay
            
    def canMove(self, xDelta, yDelta):
        if xDelta < -1 or xDelta > +1:
            return False, "Movement is one unit at a time."
        elif yDelta < -1 or yDelta > +1:
            return False, "Movement is one unit at a time."
        # get land at x+xDelta, y+yDelta
        # if land not in self.mobility, return False
        if time.time() - self.timestamp < self.mobility[landType]:
            return False, "Not yet ready to move"
        return True, ""
    
    def move(self, xDelta, yDelta):
        if canMove(xDelta, yDelta)[0]:
            self.locationX += xDelta
            self.locationY += yDelta
            self.timestamp = time.time()