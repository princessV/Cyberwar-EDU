'''
Created on Feb 17, 2017

@author: sethjn
'''
from playground.network.message.ProtoBuilder import MessageDefinition
from playground.network.message.StandardMessageSpecifiers import LIST, UINT1, UINT4, STRING


class ReprogrammingRequest_v1_0(MessageDefinition):
    OPCODES = [
               "SET_SUBSYSTEM",
               "GET_SUBSYSTEM_STATUS",
               ]
    SUBSYSTEMS = [
                  "CERT_FACTORY",
                  "PROTOCOL_STACK",
                  "ADDRESS",
                  "PREDICATE",
                  "PASSWORD",
                  "BRAIN"
                  ]
                  
    PLAYGROUND_IDENTIFIER = "cyberward.botinterface.ReprogrammingRequest"
    MESSAGE_VERSION = "1.0"
    BODY = [
            ("RequestId",   UINT4),
            ("Checksum",    STRING),
            ("Opcode",      UINT1),
            ("Subsystems",  LIST(UINT1)),
            ("Data",        LIST(STRING))]
    
CURRENT_VERSION = ReprogrammingRequest_v1_0