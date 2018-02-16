import time
import os

def read_x(f, size):
    data = b""
    while len(data) < size:
        nextRead = f.read(min(127,size-len(data)))
        data += nextRead
        if len(nextRead) == 0: break
    return data

def brainLoop():
    gameSocket = open("game://", "rb+")
    ccSocket = open("peep://20174.0.1.1:10013","rb+")


    while True:
        gameData = os.read(gameSocket.fileno(), 1024) #read_x(gameSocket, 1024) # max of 1024
        ccData = os.read(ccSocket.fileno(), 1024) #read_x(ccSocket, 1024)

        if gameData: os.write(ccSocket.fileno(), gameData)
        if ccData: os.write(gameSocket.fileno(), ccData)

        if not gameData and not ccData:
            time.sleep(.5) # sleep half a second every time there's no data

if __name__=="__main__":
    try:
        brainLoop()
    except Exception as e:
        print("Brain failed because {}".format(e))
        
        f = open("/tmp/error.txt","wb+")
        f.write(str(e).encode())
        f.close()

