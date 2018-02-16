'''
Created on Feb 15, 2018

@author: seth_
'''

import asyncio
from concurrent.futures import TimeoutError
import translations

import playground

gLOOP = None
gOBJECT_IDENTIFIER = None

class GeneralConnectionProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self._rBuffer = []
        
    def connection_made(self, transport):
        self.transport = transport
        
    def data_received(self, data):
        gLOOP.call_soon_threadsafe(self.data_received_otherthread, data)
        
    def data_received_otherthread(self, data):
        self._rBuffer.append(data)
        
    def connection_lost(self, reason=None):
        self.transport = None
        
    def closed(self):
        return self.transport == None
    
    def recv(self, maxSize=1024):
        if self._rBuffer:
            chunk = self._rBuffer[0]
            if len(chunk) > maxSize:
                chunk, self._rBuffer[0] = chunk[:maxSize], chunk[maxSize:]
            else:
                self._rBuffer.pop(0)
            return chunk
        if self.closed():
            raise Exception("Connection Closed")
        return b"" 
    
    def write(self, data):
        gLOOP.call_soon_threadsafe(self.transport.write, data)
    
    ### File Descriptor Interface for use in VFS
    def seek(self, *args):
        pass
    
    def tell(self):
        return 0
    
    def close(self):
        self.transport.close()

class GameConnectionProtocol(GeneralConnectionProtocol):
    def __init__(self):
        super().__init__()
        
    def connection_made(self, transport):
        self.transport = transport
        connectCmd = translations.BrainConnectCommand(gOBJECT_IDENTIFIER)
        transport.write(translations.BrainConnectCommand.Marshall(connectCmd))
        
class PlaygroundConnectionProtocol(GeneralConnectionProtocol):
    pass
    
async def sandbox_connect_coro(host, port):
    return await gLOOP.create_connection(GameConnectionProtocol, host=host, port=port)
    
def sandbox_connect(host, port, timeout=10):
    # ASSUME WE ARE NOT IN MAIN THREAD!!!!
    if not gOBJECT_IDENTIFIER:
        raise Exception("Cannot connect. Network not configured")
    coro = sandbox_connect_coro(host, port)
    future = asyncio.run_coroutine_threadsafe(coro, gLOOP)
    transport, protocol = future.result(timeout)
    return protocol

async def playground_connect_coro(host, port, connector):
    return await playground.create_connection(PlaygroundConnectionProtocol, 
                                              host=host, 
                                              port=port, 
                                              family=connector)

def playground_connect(host, port, connector, timeout=10):
    # ASSUME WE ARE NOT IN MAIN THREAD!!!!
    coro = playground_connect_coro(host, port, connector)
    future = asyncio.run_coroutine_threadsafe(coro, gLOOP)
    transport, protocol = future.result(timeout)
    return protocol
    