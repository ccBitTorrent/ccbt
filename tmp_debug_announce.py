import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import ccbt.session.announce as ann
from ccbt.session.announce import AnnounceLoop
from ccbt.session.session import AsyncTorrentSession, TorrentSessionInfo
import ccbt.session.peers as peers

class L:
    def info(self,*args,**kwargs):print('INFO',*args)
    def warning(self,*args,**kwargs):print('WARN',*args)
    def error(self,*args,**kwargs):print('ERR',*args)
    def debug(self,*args,**kwargs):print('DBG',*args)


td={'name':'test','info_hash':b'1'*20,'announce':'http://tracker.example.com/announce','pieces_info':{'num_pieces':0,'piece_length':0,'piece_hashes':[], 'total_length':0},'file_info':{'total_length':0}}
s=AsyncTorrentSession(td,'.')
s.logger=L(); s._stop_event=asyncio.Event(); s.config.network.announce_interval=0.01
if not hasattr(s,'info') or s.info is None: s.info=TorrentSessionInfo(info_hash=b'1'*20,name='test',status='downloading')

lr=SimpleNamespace(ip='9.0.0.1',port=6882,ssl_capable=False)
hr=SimpleNamespace(ip='1.0.0.1',port=6881,ssl_capable=False)
hr_resp=SimpleNamespace(peers=[hr],complete=100,incomplete=0,interval=30)
lr_resp=SimpleNamespace(peers=[lr],complete=0,incomplete=100,interval=30)
async def announce_to_multiple(_td,_urls,port=None,event=''):
    print('announce_to_multiple called with', _td, _urls, port, event)
    return [hr_resp, lr_resp]

s.tracker=type('T',(),{'announce_to_multiple':announce_to_multiple})()

def collect_trackers(_td):
    return ['http://tracker.example.com/announce']
from ccbt.session.announce import AnnounceController
AnnounceController.collect_trackers=collect_trackers
s.get_swarm_recovery_state=AsyncMock(return_value={'active_peers':0,'productive_peers':0,'requestable_peers':0,'peers_with_piece_info':0})
class H:
    def __init__(self,_):
        print('helper init')
    async def connect_peers_to_download(self,p):
        print('connect',p)
peers.PeerConnectionHelper=H
s.download_manager=SimpleNamespace(peer_manager=SimpleNamespace(), _download_started=True)
orig_sleep=asyncio.sleep
ann.asyncio.sleep=lambda sec: orig_sleep(min(sec,0.01))

async def main():
    loop=AnnounceLoop(s)
    t=asyncio.create_task(loop.run())
    await asyncio.sleep(0.2)
    s._stop_event.set(); t.cancel()
    try: await t
    except asyncio.CancelledError: print('cancel')

asyncio.run(main())
