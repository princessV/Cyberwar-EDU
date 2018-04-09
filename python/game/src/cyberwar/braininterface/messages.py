'''
Created on Apr 2, 2018

@author: seth_
'''

from ..core.messages import Request, Response, Event


BRAIN_INTERFACE_LAYER_NAME = "braininterface"

class CreateBrainControlledObjectRequest(Request):
    def __init__(self, sender, brainDir, *attributes):
        super().__init__(sender, BRAIN_INTERFACE_LAYER_NAME,
                         BrainDir=brainDir, Attributes=attributes)
        
class CreateBrainControlledObjectResponse(Response):
    pass

class GetBrainObjectByIdentifier(Request):
    def __init__(self, sender, identifier):
        super().__init__(sender, BRAIN_INTERFACE_LAYER_NAME,
                         Identifier=identifier)
        
class GetBrainObjectResponse(Response):
    pass

class ReprogramBrainRequest(Request):
    def __init__(self, sender, technician, reprogramTarget, brainZip):
        super().__init__(sender, BRAIN_INTERFACE_LAYER_NAME,
                         Technician=technician,
                         Target=reprogramTarget,
                         BrainZip=brainZip)
        
class DownloadBrainRequest(Request):
    def __init__(self, sender, technician, repairTarget):
        super().__init__(sender, BRAIN_INTERFACE_LAYER_NAME,
                         Technician=technician,
                         Target=repairTarget)
           
class ReprogramBrainEvent(Event):
    def __init__(self, receiver, object, target, successful, message):
        super().__init__(BRAIN_INTERFACE_LAYER_NAME, receiver,
                         Object=object, Target=target,
                         Successful=successful, Message=message)
        
class DownloadBrainEvent(Event):
    def __init__(self, receiver, object, target, brain, message):
        super().__init__(BRAIN_INTERFACE_LAYER_NAME, receiver,
                         Object=object, Target=target,
                         Brain=brain, Message=message)
        
class CreateBotRequest(Request):
    def __init__(self, sender, object, direction, designName, name, address, brainZip):
        super().__init__(sender, BRAIN_INTERFACE_LAYER_NAME,
                         Builder=object,
                         Direction=direction,
                         DesignName=designName, Name=name,
                         Address=address, BrainZip=brainZip)
        
class CreateBotResponse(Response):
    pass