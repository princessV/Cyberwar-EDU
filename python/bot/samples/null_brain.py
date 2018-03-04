import time
import os
import translations

def getNextMessage(translator, buffer):
    complete, mData = translator.HasMessage(buffer)
    if not complete:
        return None, buffer
    mt, m, headers, hOff, bLen = mData
    body, buffer = buffer[hOff:hOff+bLen], buffer[hOff+bLen:]
    msg = translator.unmarshallFromNetwork(mt, m, headers, body)
    return msg, buffer

def brainLoop():
    gameSocket = open("game://", "rb+")
#% TEMPLATE-ON
    ccSocketName = "{prot}://{host}:{port}"
#% TEMPLATE-OFF
    try:
        ccSocket = open(ccSocketName,"rb+")
    except:
        ccSocket = None

    loop = 0
    
    translator = translations.NetworkTranslator()
    hb = None
    gameDataStream = b""

    while True:
        loop += 1
        gameData = os.read(gameSocket.fileno(), 1024) # max of 1024
        gameDataStream += gameData
        if gameDataStream:
            msg, gameDataStream = getNextMessage(translator, gameDataStream)
            if isinstance(msg, translations.BrainConnectResponse):
                translator = translations.NetworkTranslator(*msg.attributes)
                hb = msg
        if (not gameData) and hb and (loop % 30 == 0) and ccSocket:
            # every thirty seconds, send heartbeat to cc
            try:
                os.write(ccSocket.fileno(), translator.marshallToNetwork(hb))
            except:
                ccSocket = None
        
        try:            
            if ccSocket:
                ccData = os.read(ccSocket.fileno(), 1024)
            else:
                ccData = b""
        except:
            ccData = b""
            ccSocket = None 

        if gameData and ccSocket:
            try: 
                os.write(ccSocket.fileno(), gameData)
            except:
                ccSocket = None
        if ccData: os.write(gameSocket.fileno(), ccData)

        if not gameData and not gameDataStream and not ccData:
            time.sleep(.5) # sleep half a second every time there's no data
            
        if not ccSocket and loop % 60 == 0:
            # if the gamesock didn't open or is dead, try to reconnect
            # once per minute
            try:
                ccSocket = open(ccSocketName, "rb+")
            except:
                ccSocket = None

if __name__=="__main__":
    try:
        brainLoop()
    except Exception as e:
        print("Brain failed because {}".format(e))
        
        f = open("/tmp/error.txt","wb+")
        f.write(str(e).encode())
        f.close()

