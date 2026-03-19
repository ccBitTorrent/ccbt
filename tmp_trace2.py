import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo
from ccbt.session.announce import AnnounceController, AnnounceLoop

class L:
    def info(self,*a,**k):
        pass
    def warning(self,*a,**k):
        pass
    def error(self,*a,**k):
        pass
    def debug(self,*a,**k):
        pass

def tracefunc(frame, event, arg):
    if frame.f_code.co_filename.endswith('announce.py'):
        if event == 'exception':
            et,ev,tb = arg
            print('EXC', frame.f_code.co_name, frame.f_lineno, et.__name__, ev)
    return tracefunc

sys.settrace(tracefunc)


td={
    "name": "test",
    "info_hash": b"1"*20,
    "announce": "http://tracker.example.com/announce",
    "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
    "file_info": {"total_length": 0},
}
session = AsyncTorrentSession(td, ".")
session._stop_event = asyncio.Event()
session.config.network.announce_interval = 0.01
session.logger = L()
if not hasattr(session, 'info') or session.info is None:
    session.info = TorrentSessionInfo(info_hash=b"1"*20, name='test', status='downloading')

low_ratio_peer = SimpleNamespace(ip='9.0.0.1', port=6882, ssl_capable=False)
high_ratio_peer = SimpleNamespace(ip='1.0.0.1', port=6881, ssl_capable=False)
high_ratio_response = SimpleNamespace(peers=[high_ratio_peer], complete=100, incomplete=0, interval=30)
low_ratio_response = SimpleNamespace(peers=[low_ratio_peer], complete=0, incomplete=100, interval=30)

async def announce_to_multiple(_td,_urls,port=None,event=''):
    print('announce called')
    return [high_ratio_response, low_ratio_response]

session.tracker = type('T', (), {'announce_to_multiple': announce_to_multiple})()

def collect_trackers(self,_td):
    print('collect called')
    return ['http://tracker.example.com/announce']

AnnounceController.collect_trackers = collect_trackers
session.get_swarm_recovery_state = AsyncMock(return_value={
    "active_peers":0,
    "productive_peers":0,
    "requestable_peers":0,
    "peers_with_piece_info":0,
})

connected = []
class _Mock:
    def __init__(self,_session):
        print('helper init')
    async def connect_peers_to_download(self, peers):
        print('connect called', peers)
        connected.append(peers)

import ccbt.session.peers as peers
peers.PeerConnectionHelper = _Mock
session.download_manager = SimpleNamespace(peer_manager=SimpleNamespace(), _download_started=True)

import ccbt.session.announce as ann
orig_sleep = asyncio.sleep
async def fast_sleep(secs):
    await orig_sleep(min(secs, 0.01))
ann.asyncio.sleep = fast_sleep

async def main():
    loop = AnnounceLoop(session)
    task = asyncio.create_task(loop.run())
    await orig_sleep(0.2)
    session._stop_event.set()
    task.cancel()
    try:
        await task
    except Exception as e:
        print('outer', type(e), e)
    print('connected', connected)

asyncio.run(main())
