'''
Created on Feb 17, 2017

@author: sethjn
'''

from playground.network.message.ProtoBuilder import MessageDefinition
from playground.network.message.StandardMessageSpecifiers import LIST, UINT4, STRING


class ReprogrammingResponse_v1_0(MessageDefinition):
    
    GENERAL_ERROR_TEMPLATE = "100. General Error. Server Reported: %(ERROR_MSG)s"
    
    REPROGRAMMING_SUCCESSFUL_TEMPLATE = "200. Reprogramming Successful (MD5=%(MD5)s) for subsystem %(SUBSYSTEM)s. Server Reported: %(MSG)s"
    REPROGRAMMING_FAILED_TEMPLATE = "300. Reprogramming Failed for subsystem %(SUBSYSTEM)s. Server Reported: %(MSG)s"
    
    STATUS_CHECK_TEMPLATE = "400. Status Check for subsystem %(SUBSYSTEM)s. MD5=%(MD5)s. Server Reported: %(MSG)s"
    
                  
    PLAYGROUND_IDENTIFIER = "cyberward.botinterface.ReprogrammingResponse"
    MESSAGE_VERSION = "1.0"
    BODY = [
            ("RequestId",   UINT4),
            ("Checksum",    STRING),
            ("Data",        LIST(STRING))]
    
CURRENT_VERSION = ReprogrammingResponse_v1_0