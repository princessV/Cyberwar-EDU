'''
Created on Feb 17, 2017

@author: sethjn
'''

from ..common.network import ReprogrammingRequest, ReprogrammingResponse
from ..common.util import FingerPrint

from twisted.internet.protocol import Protocol
from playground.network.common.Protocol import MessageStorage

from playground.network.common.Timer import OneshotTimer

class ReprogrammingProtocol(Protocol):
    def __init__(self):
        self.__storage = MessageStorage(ReprogrammingRequest)
        
    def dataReceived(self, data):
        self.__storage.update(data)
        for message in self.__storage.iterateMessages():
            checksum = message.Checksum
            message.Checksum = self.factory.password()
            messageBytes = message.__serialize__()
            messageChecksum = FingerPrint(messageBytes)
            
            # CHECK FOR ERRORS
            if checksum != messageChecksum:
                return self.sendError(message.RequestId, "Checksum mismatch. Expected %s but got %s" % (messageChecksum, checksum))
            if message.Opcode < 0 or message.Opcode >= len(ReprogrammingRequest.OPCODES):
                return self.sendError(message.RequestId, "Unknown Opcode %d" % message.Opcode)
            for subsystem in message.Subsystems:
                if subsystem < 0 or subsystem >= len(ReprogrammingRequest.SUBSYSTEMS):
                    return self.sendError(message.RequestId, "Unknown Subsystem %d" % subsystem)
                
            # SEEMS LEGIT
            if ReprogrammingRequest.OPCODES[message.Opcode] == "SET_SUBSYSTEM":
                if len(message.Subsystems) != len(message.Data):
                    return self.sendError(message.RequestId, "Bad Packet. Subsystem and Data length not the same")
                results = []
                for i in range(len(message.Subsystems)):
                    subsystem = ReprogrammingRequest.SUBSYSTEMS[message.Subsystems[i]]
                    subsystemProgram = message.Data[i]
                    success, fingerPrint, reprogramMessage = self.factory.reprogram(self, subsystem, subsystemProgram)
                    print "got result for subsystem", subsystem,success, reprogramMessage
                    results.append((subsystem, fingerPrint, success, reprogramMessage))
                self.sendReprogrammingResult(message.RequestId, results)
                t = OneshotTimer(self.factory.reload)
                t.run(1.0) # give time to process data before potentially closing connection for reload
            elif ReprogrammingRequest.OPCODES[message.Opcode] == "GET_SUBSYSTEM_STATUS":
                results = []
                for i in range(len(message.Subsystems)):
                    subsystem = ReprogrammingRequest.SUBSYSTEMS[message.Subsystems[i]]
                    success, subsystemFingerprint, subsystemStatus = self.factory.subsystemStatus(subsystem)
                    results.append((subsystem, subsystemFingerprint, subsystemStatus))
                self.sendStatus(message.RequestId, results)
            else:
                # TODO: Log the error. This is a programming error
                pass
    
    def sendError(self, requestId, errorMessage):
        response = ReprogrammingResponse(RequestId=requestId, Checksum=self.factory.password())
        response.Data = [ReprogrammingResponse.GENERAL_ERROR_TEMPLATE % {"ERROR_MSG": errorMessage}]
        checksum = FingerPrint(response.__serialize__())
        response.Checksum = checksum
        self.transport.write(response.__serialize__())
        
    def sendReprogrammingResult(self, requestId, results):
        response = ReprogrammingResponse(RequestId=requestId, Checksum=self.factory.password())
        responseData = []
        for subsystem, subsystemHash, subsystemSuccess, subsystemMsg in results:
            msgDb = {"MD5": subsystemHash, "SUBSYSTEM": subsystem, "MSG": subsystemMsg}
            if subsystemSuccess:
                responseData.append(ReprogrammingResponse.REPROGRAMMING_SUCCESSFUL_TEMPLATE % msgDb)
            else:
                responseData.append(ReprogrammingResponse.REPROGRAMMING_FAILED_TEMPLATE % msgDb)
        response.Data = responseData
        checksum = FingerPrint(response.__serialize__())
        response.Checksum = checksum
        print self, self.transport, "send reprogram result for id", requestId, len(response.__serialize__()), "bytes"
        self.transport.write(response.__serialize__())
        
    def sendStatus(self, requestId, results):
        response = ReprogrammingResponse(RequestId=requestId, Checksum=self.factory.password())
        responseData = []
        for subsystem, subsystemHash, subsystemMsg in results:
            msgDb = {"MD5": subsystemHash, "SUBSYSTEM": subsystem, "MSG": subsystemMsg}
            responseData.append(ReprogrammingResponse.STATUS_CHECK_TEMPLATE % msgDb)
        response.Data = responseData
        checksum = FingerPrint(response.__serialize__())
        response.Checksum = checksum
        self.transport.write(response.__serialize__())