'''
Created on Feb 15, 2018

@author: seth_
'''

import asyncio, subprocess, os, sys
from concurrent.futures import TimeoutError
import translations

import playground

gLOOP = None
gOBJECT_IDENTIFIER = None
PLAYGROUND_CFG_PATH = None # used to make sure we stay within right playground

class RestartRequest:
    Status = False

class GeneralConnectionProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self._rBuffer = []
        self._messageBuffer = b""
        # create a network translator for special commands
        self._translator = translations.NetworkTranslator()
        
    def connection_made(self, transport):
        self.transport = transport
        
    def data_received(self, data):
        gLOOP.call_soon_threadsafe(self.data_received_otherthread, data)
        
    def _handleMessage(self, mt, m, headers, body):
        return False
        
    def data_received_otherthread(self, data):
        self._messageBuffer += data
        while self._messageBuffer:
            try:
                res = translations.NetworkTranslator.HasMessage(self._messageBuffer)
                complete, meta = res
            except Exception as e:
                print("Failed", e)
                self._messageBuffer = b""
                return
            if not complete:
                return
            mt, m, headers, hOff, blen = meta
            offset = hOff + blen
            message, self._messageBuffer = self._messageBuffer[:offset], self._messageBuffer[offset:]
            if not self._handleMessage(mt, m, headers, message[hOff:]):
                #print("Standard handling:",mt, m)
                self._rBuffer.append(message)
        
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
    
    def _writeWrapper(self, data):
        try:
            self.transport.write(data)
        except:
            try:
                self.transport.close()
            except:
                pass
            self.transport=None
    
    def write(self, data):
        # if we're already closed, throw an exception immediately
        if self.closed():
            raise Exception("Connection closed")
        gLOOP.call_soon_threadsafe(self._writeWrapper, data)
    
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
    def _handleMessage(self, mt, m, headers, body):
        #print(b"CMD", translations.ReprogramCommand.CMD)
        if mt == b"CMD" and m == translations.ReprogramCommand.CMD:
            try:
                cmd = self._translator.unmarshallFromNetwork(mt, m, headers, body)
                # go up one path from .playground. That's root.
                rootPath = os.path.abspath(os.path.join(PLAYGROUND_CFG_PATH, ".."))
                filePath = os.path.abspath(os.path.join(rootPath, cmd.path))
                # check that the abspath is under root:
                # in other words, make sure they didnt do /a/b/c/../../../x
                if not filePath.startswith(rootPath):
                    raise Exception("Invalid path")
                
                dirPath = os.path.dirname(filePath)
                if not os.path.exists(dirPath):
                    os.makedirs(dirPath)
                if len(body) == 0 and cmd.deleteFile:
                    if os.path.exists(filePath):
                        print("delete")
                        os.unlink(filePath)
                    else:
                        raise Exception("Can't delete non-existant file")
                else:
                    with open(filePath, "wb+") as f:
                        f.write(body)
                if cmd.restartNetworking:
                    subprocess.call("pnetworking off", shell=True, cwd=rootPath)
                    subprocess.call("pnetworking on", shell=True, cwd=rootPath)
                if cmd.restartBrain:
                    # Another hack. We don't have a good message system back to the brain_interact script. Think of one.
                    RestartRequest.Status = True
                response = translations.ReprogramResponse(cmd.path, True, "Reprogramming complete")
                self.transport.write(self._translator.marshallToNetwork(response))
                return True # this means it won't be sent up to the brain.
            except Exception as e:
                print("Could not unmarshall message because", e)
                response = translations.ReprogramResponse(cmd.path, False, "Could not do it {}".format(e))
                self.transport.write(self._translator.marshallToNetwork(response))
                return True
    
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

async def playground_connect_coro(host, port, connector, timeout):
    return await playground.getConnector(connector).create_playground_connection(PlaygroundConnectionProtocol, 
                                              host, 
                                              port, 
                                              timeout=timeout)

def playground_connect(host, port, connector, timeout=10):
    print("*******playground connect")
    # make sure that we're still using the brain-configured pnetworking
    # we aren't isolated. if the brain delets it's networking.ini, it
    # will revert to a global networking.ini, breaking the sandbox
    if PLAYGROUND_CFG_PATH is None:
        raise Exception("Playground not configured")
    elif playground.Configure.CurrentPath() != PLAYGROUND_CFG_PATH:
        print(os.getcwd())
        print(playground.Configure.CurrentPath())
        raise Exception("No valid playground configuration")
    print("do playground connection using data in", playground.Configure.CurrentPath())
    # ASSUME WE ARE NOT IN MAIN THREAD!!!!
    coro = playground_connect_coro(host, port, connector, timeout)
    future = asyncio.run_coroutine_threadsafe(coro, gLOOP)
    try:
        transport, protocol = future.result()
    except asyncio.TimeoutError:
        print("Cancel playground connect")
        res = future.cancel()
        print("Cancel = {}".format(res))
        raise Exception("Could not connect to playground {}:{} in {} seconds.".format(host, port, timeout))
    print("Connected to playground on {}".format(transport.get_extra_info("sockname")))
    return protocol
    