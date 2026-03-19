import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo
from ccbt.session.announce import AnnounceController, AnnounceLoop

class L:
    def info(self,*a,**k): pass
    def warning(self,*a,**k): pass
    def error(self,*a,**k): pass
    def debug(self,*a,**k): pass


def tracefunc(frame, event, arg):
    if frame.f_code.co_filename.endswith("announce.py"):
        if event == 'exception':
            et,ev,tb = arg
            print('TRACE_EXC at', frame.f_lineno, et.__name__, ev)
    return tracefunc

sys.settrace(tracefunc)


td = {
    "name":"test",
    "info_hash": b"1"*20,
    "announce": "http://tracker.example.com/announce",
    "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
    "file_info": {"total_length": 0},
}
s=AsyncTorrentSession(td, ".")
s.logger=L()
s._stop_event=asyncio.Event()
s.config.network.announce_interval=0.01
if not hasattr(s,'info') or s.info is None:
    s.info=TorrentSessionInfo(info_hash=b"1"*20,name='test',status='downloading')

low_ratio_peer=SimpleNamespace(ip='9.0.0.1',port=6882,ssl_capable=False)
high_ratio_peer=SimpleNamespace(ip='1.0.0.1',port=6881,ssl_capable=False)
high_ratio_response=SimpleNamespace(peers=[high_ratio_peer], complete=100,incomplete=0,interval=30)
low_ratio_response=SimpleNamespace(peers=[low_ratio_peer], complete=0,incomplete=100,interval=30)

async def announce_to_multiple(_td, _urls, port=None, event=''):
    return [high_ratio_response, low_ratio_response]

s.tracker = type('T', (), {'announce_to_multiple': announce_to_multiple})()

def collect_trackers(_td):
    return ['http://tracker.example.com/announce']

AnnounceController.collect_trackers = collect_trackers
s.get_swarm_recovery_state = AsyncMock(return_value={"active_peers":0,"productive_peers":0,"requestable_peers":0,"peers_with_piece_info":0})

connected=[]
class P:
    def __init__(self,_):
        print('helper init')
    async def connect_peers_to_download(self, peers):
        print('connect', peers)
        connected.append(peers)

import ccbt.session.peers as peersmod
peersmod.PeerConnectionHelper = P
s.download_manager = SimpleNamespace(peer_manager=SimpleNamespace(), _download_started=True)

import ccbt.session.announce as ann
orig_sleep=ann.asyncio.sleep
async def fast(secs):
    await orig_sleep(0.01)
ann.asyncio.sleep=fast

async def main():
    loop=AnnounceLoop(s)
    t=asyncio.create_task(loop.run())
    await asyncio.sleep(0.2)
    s._stop_event.set()
    t.cancel()
    try:
        await t
    except Exception as e:
        print('outer caught',type(e),e)

asyncio.run(main())
