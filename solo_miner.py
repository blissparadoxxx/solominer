#!/usr/bin/env python  
# Copyright (c) 2021-2022 iceland
# Copyright (c) 2022-2023 Papa Crouz
# Distributed under the MIT/X11 software license, see the accompanying
# file license http://www.opensource.org/licenses/mit-license.php.


from signal import signal, SIGINT
import context as ctx 
import traceback 
import threading
import requests 
import binascii
import hashlib
import logging
import random
import socket
import time
import json
import sys
import os




# Replace this with your Bitcoin Address
address = 'bc1qh9ym45jspae773zulehxup258ykgn4uqjwwdy2'





def handler(signal_received, frame):
    # Handle any cleanup here
    ctx.fShutdown = True
    print('Terminating miner, please wait..')



def logg(msg):
    # basic logging 
    logging.basicConfig(level=logging.INFO, filename="miner.log", format='%(asctime)s %(message)s') # include timestamp
    logging.info(msg)





def get_current_block_height():
    # returns the current network height 
    r = requests.get('https://blockchain.info/latestblock')
    return int(r.json()['height'])


def calculate_hashrate(nonce, last_updated):
  if nonce % 1000000 == 999999:
    now             = time.time()
    hashrate        = round(1000000/(now - last_updated))
    sys.stdout.write("\r%s hash/s"%(str(hashrate)))
    sys.stdout.flush()
    return now
  else:
    return last_updated



def check_for_shutdown(t):
    # handle shutdown 
    n = t.n
    if ctx.fShutdown:
        if n != -1:
            ctx.listfThreadRunning[n] = False
            t.exit = True



class ExitedThread(threading.Thread):
    def __init__(self, arg, n):
        super(ExitedThread, self).__init__()
        self.exit = False
        self.arg = arg
        self.n = n

    def run(self):
        self.thread_handler(self.arg, self.n)
        pass

    def thread_handler(self, arg, n):
        while True:
            check_for_shutdown(self)
            if self.exit:
                break
            ctx.listfThreadRunning[n] = True
            try:
                self.thread_handler2(arg)
            except Exception as e:
                logg("ThreadHandler()")
                logg(e)
            ctx.listfThreadRunning[n] = False

            time.sleep(5)
            pass

    def thread_handler2(self, arg):
        raise NotImplementedError("must impl this func")

    def check_self_shutdown(self):
        check_for_shutdown(self)

    def try_exit(self):
        self.exit = True
        ctx.listfThreadRunning[self.n] = False
        pass






def bitcoin_miner(t, restarted=False):

    if restarted:
        logg('[*] Bitcoin Miner restarted')
        time.sleep(10)




    target = (ctx.nbits[2:]+'00'*(int(ctx.nbits[:2],16) - 3)).zfill(64)
    ctx.extranonce2 = hex(random.randint(0,2**32-1))[2:].zfill(2*ctx.extranonce2_size)      # create random

    coinbase = ctx.coinb1 + ctx.extranonce1 + ctx.extranonce2 + ctx.coinb2
    coinbase_hash_bin = hashlib.sha256(hashlib.sha256(binascii.unhexlify(coinbase)).digest()).digest()

    merkle_root = coinbase_hash_bin
    for h in ctx.merkle_branch:
        merkle_root = hashlib.sha256(hashlib.sha256(merkle_root + binascii.unhexlify(h)).digest()).digest()

    merkle_root = binascii.hexlify(merkle_root).decode()

    #little endian
    merkle_root = ''.join([merkle_root[i]+merkle_root[i+1] for i in range(0,len(merkle_root),2)][::-1])

    work_on = get_current_block_height()


    ctx.nHeightDiff[work_on+1] = 0 



    _diff = int("00000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF", 16)

    




    logg('[*] Working to solve block with height {}'.format(work_on+1))





    if len(sys.argv) > 1:
        random_nonce = False 
    else:
        random_nonce = True

    

    nNonce = 0 


    last_updated = int(time.time())




    while True:
        t.check_self_shutdown()
        if t.exit:
            break

        if ctx.prevhash != ctx.updatedPrevHash:
            logg('[*] New block {} detected on network '.format(ctx.prevhash))
            logg('[*] Best difficulty will trying to solve block {} was {}'.format(work_on+1, ctx.nHeightDiff[work_on+1]))
            ctx.updatedPrevHash = ctx.prevhash
            bitcoin_miner(t, restarted=True)
            break 


        if random_nonce:
            nonce = hex(random.randint(0,2**32-1))[2:].zfill(8) # nNonce   #hex(int(nonce,16)+1)[2:]
        else:
            nonce = hex(nNonce)[2:].zfill(8)

        #The standard Bitcoin block header is exactly 80 bytes (not 128).
        #If you hash an 80-byte input and a 128-byte input, the outputs will differ.
        #this is ck pool found block https://mempool.space/block/000000000000000000008659827d9d3e3f98cb6428ce5149464b44125be5ce19?showDetails=true&view=actual#details
        #and this block header for that block  https://mempool.space/api/block/000000000000000000008659827d9d3e3f98cb6428ce5149464b44125be5ce19/header

        blockheader = ctx.version + ctx.prevhash + merkle_root + ctx.ntime + ctx.nbits + nonce
        
        # Test
        #blockheader = "00000034a701be3e9898775007c26f5f956db38ad858465828a500000000000000000000482eb3d98241ac8bb925d6419a20d67d1a79e3f217b21805776f9ca537fad3809fe96667fa970217bf573cce" 
        hash = hashlib.sha256(hashlib.sha256(binascii.unhexlify(blockheader)).digest()).digest()
        hash = binascii.hexlify(hash).decode()
        hash = "".join(reversed([hash[i:i+2] for i in range(0, len(hash), 2)]))
        # if test blokheader print(hash) 
        # you will get same hash 000000000000000000008659827d9d3e3f98cb6428ce5149464b44125be5ce19

        # Logg all hashes that start with 7 zeros or more
        if hash.startswith('0000000'): logg('[*] New hash: {} for block {}'.format(hash, work_on+1))



        this_hash = int(hash, 16)

        difficulty = _diff / this_hash


        if ctx.nHeightDiff[work_on+1] < difficulty:
            # new best difficulty for block at x height
            ctx.nHeightDiff[work_on+1] = difficulty
        

        if not random_nonce:
            # hash meter, only works with regular nonce.
            last_updated = calculate_hashrate(nNonce, last_updated)




        if hash < target :
            logg('[*] Block {} solved.'.format(work_on+1))
            logg('[*] Block hash: {}'.format(hash))
            logg('[*] Blockheader: {}'.format(blockheader))            
            payload = bytes('{"params": ["'+address+'", "'+ctx.job_id+'", "'+ctx.extranonce2 \
                +'", "'+ctx.ntime+'", "'+nonce+'"], "id": 1, "method": "mining.submit"}\n', 'utf-8')
            logg('[*] Payload: {}'.format(payload))
            ctx.sock.sendall(payload)
            ret = ctx.sock.recv(1024)
            logg('[*] Pool response: {}'.format(ret))
            return True
        
        # increment nonce by 1, in case we don't want random 
        nNonce +=1



       


def block_listener(t):
    
    # init a connection to ckpool 
    sock  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('solo.ckpool.org', 3333))
    # send a handle subscribe message 
    sock.sendall(b'{"id": 1, "method": "mining.subscribe", "params": []}\n')
    lines = sock.recv(1024).decode().split('\n')
    response = json.loads(lines[0])
    ctx.sub_details,ctx.extranonce1,ctx.extranonce2_size = response['result']
    # send and handle authorize message  
    sock.sendall(b'{"params": ["'+address.encode()+b'", "password"], "id": 2, "method": "mining.authorize"}\n')
    response = b''
    while response.count(b'\n') < 4 and not(b'mining.notify' in response):response += sock.recv(1024)

    responses = [json.loads(res) for res in response.decode().split('\n') if len(res.strip())>0 and 'mining.notify' in res]
    ctx.job_id, ctx.prevhash, ctx.coinb1, ctx.coinb2, ctx.merkle_branch, ctx.version, ctx.nbits, ctx.ntime, ctx.clean_jobs = responses[0]['params']
    # do this one time, will be overwriten by mining loop when new block is detected
    ctx.updatedPrevHash = ctx.prevhash
    # set sock 
    ctx.sock = sock 


    while True:
        t.check_self_shutdown()
        if t.exit:
            break


        # check for new block 
        response = b''
        while response.count(b'\n') < 4 and not(b'mining.notify' in response):response += sock.recv(1024)
        responses = [json.loads(res) for res in response.decode().split('\n') if len(res.strip())>0 and 'mining.notify' in res]     
        

        if responses[0]['params'][1] != ctx.prevhash:
            # new block detected on network 
            # update context job data 
            ctx.job_id, ctx.prevhash, ctx.coinb1, ctx.coinb2, ctx.merkle_branch, ctx.version, ctx.nbits, ctx.ntime, ctx.clean_jobs = responses[0]['params']
            





class CoinMinerThread(ExitedThread):
    def __init__(self, arg=None):
        super(CoinMinerThread, self).__init__(arg, n=0)

    def thread_handler2(self, arg):
        self.thread_bitcoin_miner(arg)

    def thread_bitcoin_miner(self, arg):
        ctx.listfThreadRunning[self.n] = True
        check_for_shutdown(self)
        try:
            ret = bitcoin_miner(self)
            logg("[*] Miner returned %s\n\n" % "true" if ret else"false")
        except Exception as e:
            logg("[*] Miner()")
            logg(e)
            traceback.print_exc()
        ctx.listfThreadRunning[self.n] = False

    pass  




class NewSubscribeThread(ExitedThread):
    def __init__(self, arg=None):
        super(NewSubscribeThread, self).__init__(arg, n=1)

    def thread_handler2(self, arg):
        self.thread_new_block(arg)

    def thread_new_block(self, arg):
        ctx.listfThreadRunning[self.n] = True
        check_for_shutdown(self)
        try:
            ret = block_listener(self)
        except Exception as e:
            logg("[*] Subscribe thread()")
            logg(e)
            traceback.print_exc()
        ctx.listfThreadRunning[self.n] = False

    pass  





def StartMining():
    subscribe_t = NewSubscribeThread(None)
    subscribe_t.start()
    logg("[*] Subscribe thread started.")

    time.sleep(4)

    miner_t = CoinMinerThread(None)
    miner_t.start()
    logg("[*] Bitcoin miner thread started")

    print('Bitcoin Miner started')





if __name__ == '__main__':
    signal(SIGINT, handler)




    StartMining()
