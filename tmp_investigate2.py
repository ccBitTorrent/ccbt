import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo
from ccbt.session.announce import AnnounceController, AnnounceLoop

class Logger:
    def _fmt(self, level, msg, *args):
        if args:
            try:
                msg = str(msg) % args
            except Exception:
                msg = str(msg)
        print(level + ': ' + msg)
    def info(self, msg, *args, **kwargs):
        self._fmt('INFO', msg, *args)
    def warning(self, msg, *args, **kwargs):
        self._fmt('WARN', msg, *args)
    def error(self, msg, *args, **kwargs):
        self._fmt('ERR', msg, *args)
    def debug(self, msg, *args, **kwargs):
        self._fmt('DEBUG', msg, *args)

class L(Exception):
    pass

def main_tracker(urls, td):
    pass

td={
    "name":"test",
    "info_hash": b"1"*20,
    "announce": "http://tracker.example.com/announce",
    "pieces_info": {"num_pieces": 0, "piece_length": 0, "piece_hashes": [], "total_length": 0},
    "file_info": {"total_length": 0},
}
s=AsyncTorrentSession(td, ".")
s.logger=Logger()
s._stop_event = asyncio.Event()
s.config.network.announce_interval = 0.01
if not hasattr(s,'info') or s.info is None:
    s.info = TorrentSessionInfo(info_hash=b"1"*20, name='test', status='downloading')

low_ratio_peer = SimpleNamespace(ip='9.0.0.1', port=6882, ssl_capable=False)
high_ratio_peer = SimpleNamespace(ip='1.0.0.1', port=6881, ssl_capable=False)
high_ratio_response = SimpleNamespace(peers=[high_ratio_peer], complete=100, incomplete=0, interval=30)
low_ratio_response = SimpleNamespace(peers=[low_ratio_peer], complete=0, incomplete=100, interval=30)

async def announce_to_multiple(_td, _urls, port=None, event=''):
    print('announce_to_multiple called', _td.get('name'), _urls, port, event)
    return [high_ratio_response, low_ratio_response]

s.tracker = type('T', (), {'announce_to_multiple': announce_to_multiple})()

# monkeypatch collect trackers on AnnounceController

def collect_trackers(_td):
    print('collect_trackers called')
    return ["http://tracker.example.com/announce"]

AnnounceController.collect_trackers = collect_trackers

s.get_swarm_recovery_state = AsyncMock(return_value={
    "active_peers":0,
    "productive_peers":0,
    "requestable_peers":0,
    "peers_with_piece_info":0,
})

connected_peer_lists=[]
class _MockPeerConnectionHelper:
    def __init__(self, _session):
        print('helper init', _session is not None)
    async def connect_peers_to_download(self, peers):
        print('connect_called', peers)
        connected_peer_lists.append(peers)

import ccbt.session.peers as peersmod
peersmod.PeerConnectionHelper = _MockPeerConnectionHelper

s.download_manager = SimpleNamespace(peer_manager=SimpleNamespace(), _download_started=True)

orig_sleep = asyncio.sleep
async def fast_sleep(secs):
    print('sleep', secs)
    await orig_sleep(min(secs, 0.01))
import ccbt.session.announce as announce_mod
announce_mod.asyncio.sleep = fast_sleep

async def run():
    loop = AnnounceLoop(s)
    t = asyncio.create_task(loop.run())
    await orig_sleep(0.2)
    s._stop_event.set()
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        print('loop cancelled')
    print('connected_peer_lists len', len(connected_peer_lists))
    if connected_peer_lists:
        print('first', connected_peer_lists[0])

asyncio.run(run())
