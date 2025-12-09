# ccBitTorrent - Oni BitTorrent Client ti Oṣuwọn Giga

BitTorrent client tuntun ati ti oṣuwọn giga ti a kọ pẹlu Python asyncio, pẹlu awọn algorithms iwọn ti aṣayan apakan, iyipada metadata parallel, ati I/O disk ti o dara julọ.

## Awọn ẹya

### Awọn Igbasilẹ Oṣuwọn
- **Async I/O**: Iṣẹṣe asyncio pipe fun iṣiṣẹpọ to ga julọ
- **Aṣayan Rarest-First**: Aṣayan apakan ọlọgbọn fun ilera swarm to dara julọ
- **Endgame Mode**: Awọn ibeere ti a ṣe ni ilọsiwaju fun ipari to yara
- **Pipeline Ibeere**: Awọn ẹgbẹ ibeere jinlẹ (16-64 awọn ibeere ti ko pari fun ọkọọkan peer)
- **Tit-for-Tat Choking**: Pinpin bandwidth to tọ pẹlu optimistic unchoke
- **Metadata Parallel**: Gbigba ut_metadata ni akọkọ lati ọpọlọpọ awọn peer
- **Igbasilẹ Disk I/O**: Iṣeto tẹlẹ faili, kikọ ni awọn ẹgbẹ, ring-buffer staging, memory-mapped I/O
- **Pool Ijẹrisi Hash**: Ijẹrisi SHA-1 parallel laarin awọn threads oṣiṣẹ

### Iṣeto Ijẹhin
- **Iṣeto TOML**: Ẹrọ iṣeto pipe pẹlu hot-reload
- **Awọn Iṣeto Torrent Kọọkan**: Awọn ayipada iṣeto torrent kọọkan
- **Idiwọn Iwọn**: Awọn aala agbaye ati ti torrent kọọkan ti upload/download
- **Aṣayan Strategy**: Aṣayan apakan round-robin, rarest-first, tabi ni ọna
- **Streaming Mode**: Aṣayan apakan ti o da lori ipa pataki fun awọn faili multimedia

### Awọn Ẹya Network
- **Atilẹyin UDP Tracker**: Ibaraẹnisọrọ tracker UDP ti o ni ibamu pẹlu BEP 15
- **DHT Ti o Dara**: Tabili routing Kademlia pipe pẹlu awọn wiwadi ti a tun ṣe
- **Iyipada Peer (PEX)**: Wiwa peer ti o ni ibamu pẹlu BEP 11
- **Iṣakoso Asopọ**: Aṣayan peer ti o yipada ati awọn aala asopọ
- **Awọn Igbasilẹ Protocol**: Iṣakoso oju-iwe ti o dara ti awọn ifiranṣẹ pẹlu awọn ọna zero-copy

## Afikun Protocol Xet (BEP XET)

Afikun Protocol Xet jẹ iyatọ pataki ti o yipada BitTorrent si ẹrọ faili peer-to-peer to yara pupọ, ti o le ṣe ayipada ti a dara julọ fun iṣiṣẹpọ. BEP XET gba laaye:

- **Chunking Ti a Ṣe Alaye nipasẹ Akoonu**: Pinpin faili ọlọgbọn ti o da lori Gearhash (awọn chunks 8KB-128KB) fun awọn ayipada ti o dara
- **Deduplication Laarin Torrent**: Deduplication ipele chunk laarin ọpọlọpọ awọn torrent
- **CAS Peer-to-Peer**: Ibi ipamọ Akoonu Ti o le Ṣe Alaye Ti ko ni Aarin ti o lo DHT ati awọn tracker
- **Awọn Ayipada To Yara Pupọ**: Awọn chunks ti a yipada nikan nilo lati pinpin lẹẹkansi, gbigba laaye iyipada faili iṣiṣẹpọ to yara
- **Ẹrọ Faili P2P**: Yipada BitTorrent si ẹrọ faili peer-to-peer ti o le ṣe ayipada ti a dara julọ fun iṣiṣẹpọ
- **Ijẹrisi Igi Merkle**: Hashing BLAKE3-256 pẹlu fallback SHA-256 fun ojuṣe

[Kọ ẹkọ siwaju sii nipa BEP XET →](bep_xet.md)

## Bẹrẹ Ni Yara

### Fi sori ẹrọ Pẹlu UV

Fi UV sori ẹrọ lati [astral.sh/uv](https://astral.sh/uv), lẹhinna fi ccBitTorrent sori ẹrọ.

### Awọn Ibugbe Wọle Pataki

**Bitonic** - Interface dashboard terminal pataki (a daba):
- Bẹrẹ: `uv run bitonic` tabi `uv run ccbt dashboard`

**btbt CLI** - Interface ori ila ti o dara julọ:
- Bẹrẹ: `uv run btbt`

**ccbt** - Interface CLI ti o bẹrẹ:
- Bẹrẹ: `uv run ccbt`

Fun lilo to jinlẹ, wo:
- [Itọsọna Bẹrẹ](getting-started.md) - Tutorial ni awọn igbesẹ
- [Bitonic](bitonic.md) - Itọsọna dashboard terminal
- [btbt CLI](btbt-cli.md) - Atokọ itọkasi pipe

## Iwe

- [BEP XET](bep_xet.md) - Afikun Protocol Xet fun chunking ti a ṣe alaye nipasẹ akoonu ati deduplication
- [Bẹrẹ](getting-started.md) - Fi sori ẹrọ ati awọn igbesẹ akọkọ
- [Bitonic](bitonic.md) - Dashboard terminal (interface pataki)
- [btbt CLI](btbt-cli.md) - Atokọ itọkasi interface ori ila
- [Iṣeto](configuration.md) - Awọn aṣayan iṣeto ati eto
- [Igbasilẹ Oṣuwọn](performance.md) - Itọsọna igbasilẹ
- [Atokọ itọkasi API ccBT](API.md) - Awọn iwe API Python
- [Ifowosi](contributing.md) - Bawo ni a ṣe le ṣe ifowosi
- [Ifowosi](funding.md) - Ṣe atilẹyin fun iṣẹ naa

## Iwe-aṣẹ

Iṣẹ yii ni iwe-aṣẹ labẹ **GNU General Public License v2 (GPL-2.0)** - wo [license.md](license.md) fun awọn alaye.

Ni afikun, iṣẹ yii ni idiwọn lilo afikun labẹ **Iwe-aṣẹ ccBT RAIL-AMS** - wo [ccBT-RAIL.md](ccBT-RAIL.md) fun awọn ofin pipe ati awọn idiwọn lilo.

**Pataki**: Awọn iwe-aṣẹ mejeeji ni ipa lori software yii. O gbọdọ tẹle gbogbo awọn ofin ati awọn idiwọn ni iwe-aṣẹ GPL-2.0 ati iwe-aṣẹ RAIL.

## Awọn Iroyin

Wo awọn iroyin iṣẹ ni iwe:
- [Awọn Iroyin Ikun](reports/coverage.md) - Iṣiro ikun koodu
- [Iroyin Aabo Bandit](reports/bandit/index.md) - Awọn abajade iwadii aabo
- [Awọn Ipele Oṣuwọn](reports/benchmarks/index.md) - Awọn abajade ipele oṣuwọn

## E dupe

- Apejuwe protocol BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocol Xet fun imoran chunking ti a ṣe alaye nipasẹ akoonu
- Python asyncio fun I/O oṣuwọn giga
- Agbegbe BitTorrent fun idagbasoke protocol






BitTorrent client tuntun ati ti oṣuwọn giga ti a kọ pẹlu Python asyncio, pẹlu awọn algorithms iwọn ti aṣayan apakan, iyipada metadata parallel, ati I/O disk ti o dara julọ.

## Awọn ẹya

### Awọn Igbasilẹ Oṣuwọn
- **Async I/O**: Iṣẹṣe asyncio pipe fun iṣiṣẹpọ to ga julọ
- **Aṣayan Rarest-First**: Aṣayan apakan ọlọgbọn fun ilera swarm to dara julọ
- **Endgame Mode**: Awọn ibeere ti a ṣe ni ilọsiwaju fun ipari to yara
- **Pipeline Ibeere**: Awọn ẹgbẹ ibeere jinlẹ (16-64 awọn ibeere ti ko pari fun ọkọọkan peer)
- **Tit-for-Tat Choking**: Pinpin bandwidth to tọ pẹlu optimistic unchoke
- **Metadata Parallel**: Gbigba ut_metadata ni akọkọ lati ọpọlọpọ awọn peer
- **Igbasilẹ Disk I/O**: Iṣeto tẹlẹ faili, kikọ ni awọn ẹgbẹ, ring-buffer staging, memory-mapped I/O
- **Pool Ijẹrisi Hash**: Ijẹrisi SHA-1 parallel laarin awọn threads oṣiṣẹ

### Iṣeto Ijẹhin
- **Iṣeto TOML**: Ẹrọ iṣeto pipe pẹlu hot-reload
- **Awọn Iṣeto Torrent Kọọkan**: Awọn ayipada iṣeto torrent kọọkan
- **Idiwọn Iwọn**: Awọn aala agbaye ati ti torrent kọọkan ti upload/download
- **Aṣayan Strategy**: Aṣayan apakan round-robin, rarest-first, tabi ni ọna
- **Streaming Mode**: Aṣayan apakan ti o da lori ipa pataki fun awọn faili multimedia

### Awọn Ẹya Network
- **Atilẹyin UDP Tracker**: Ibaraẹnisọrọ tracker UDP ti o ni ibamu pẹlu BEP 15
- **DHT Ti o Dara**: Tabili routing Kademlia pipe pẹlu awọn wiwadi ti a tun ṣe
- **Iyipada Peer (PEX)**: Wiwa peer ti o ni ibamu pẹlu BEP 11
- **Iṣakoso Asopọ**: Aṣayan peer ti o yipada ati awọn aala asopọ
- **Awọn Igbasilẹ Protocol**: Iṣakoso oju-iwe ti o dara ti awọn ifiranṣẹ pẹlu awọn ọna zero-copy

## Afikun Protocol Xet (BEP XET)

Afikun Protocol Xet jẹ iyatọ pataki ti o yipada BitTorrent si ẹrọ faili peer-to-peer to yara pupọ, ti o le ṣe ayipada ti a dara julọ fun iṣiṣẹpọ. BEP XET gba laaye:

- **Chunking Ti a Ṣe Alaye nipasẹ Akoonu**: Pinpin faili ọlọgbọn ti o da lori Gearhash (awọn chunks 8KB-128KB) fun awọn ayipada ti o dara
- **Deduplication Laarin Torrent**: Deduplication ipele chunk laarin ọpọlọpọ awọn torrent
- **CAS Peer-to-Peer**: Ibi ipamọ Akoonu Ti o le Ṣe Alaye Ti ko ni Aarin ti o lo DHT ati awọn tracker
- **Awọn Ayipada To Yara Pupọ**: Awọn chunks ti a yipada nikan nilo lati pinpin lẹẹkansi, gbigba laaye iyipada faili iṣiṣẹpọ to yara
- **Ẹrọ Faili P2P**: Yipada BitTorrent si ẹrọ faili peer-to-peer ti o le ṣe ayipada ti a dara julọ fun iṣiṣẹpọ
- **Ijẹrisi Igi Merkle**: Hashing BLAKE3-256 pẹlu fallback SHA-256 fun ojuṣe

[Kọ ẹkọ siwaju sii nipa BEP XET →](bep_xet.md)

## Bẹrẹ Ni Yara

### Fi sori ẹrọ Pẹlu UV

Fi UV sori ẹrọ lati [astral.sh/uv](https://astral.sh/uv), lẹhinna fi ccBitTorrent sori ẹrọ.

### Awọn Ibugbe Wọle Pataki

**Bitonic** - Interface dashboard terminal pataki (a daba):
- Bẹrẹ: `uv run bitonic` tabi `uv run ccbt dashboard`

**btbt CLI** - Interface ori ila ti o dara julọ:
- Bẹrẹ: `uv run btbt`

**ccbt** - Interface CLI ti o bẹrẹ:
- Bẹrẹ: `uv run ccbt`

Fun lilo to jinlẹ, wo:
- [Itọsọna Bẹrẹ](getting-started.md) - Tutorial ni awọn igbesẹ
- [Bitonic](bitonic.md) - Itọsọna dashboard terminal
- [btbt CLI](btbt-cli.md) - Atokọ itọkasi pipe

## Iwe

- [BEP XET](bep_xet.md) - Afikun Protocol Xet fun chunking ti a ṣe alaye nipasẹ akoonu ati deduplication
- [Bẹrẹ](getting-started.md) - Fi sori ẹrọ ati awọn igbesẹ akọkọ
- [Bitonic](bitonic.md) - Dashboard terminal (interface pataki)
- [btbt CLI](btbt-cli.md) - Atokọ itọkasi interface ori ila
- [Iṣeto](configuration.md) - Awọn aṣayan iṣeto ati eto
- [Igbasilẹ Oṣuwọn](performance.md) - Itọsọna igbasilẹ
- [Atokọ itọkasi API ccBT](API.md) - Awọn iwe API Python
- [Ifowosi](contributing.md) - Bawo ni a ṣe le ṣe ifowosi
- [Ifowosi](funding.md) - Ṣe atilẹyin fun iṣẹ naa

## Iwe-aṣẹ

Iṣẹ yii ni iwe-aṣẹ labẹ **GNU General Public License v2 (GPL-2.0)** - wo [license.md](license.md) fun awọn alaye.

Ni afikun, iṣẹ yii ni idiwọn lilo afikun labẹ **Iwe-aṣẹ ccBT RAIL-AMS** - wo [ccBT-RAIL.md](ccBT-RAIL.md) fun awọn ofin pipe ati awọn idiwọn lilo.

**Pataki**: Awọn iwe-aṣẹ mejeeji ni ipa lori software yii. O gbọdọ tẹle gbogbo awọn ofin ati awọn idiwọn ni iwe-aṣẹ GPL-2.0 ati iwe-aṣẹ RAIL.

## Awọn Iroyin

Wo awọn iroyin iṣẹ ni iwe:
- [Awọn Iroyin Ikun](reports/coverage.md) - Iṣiro ikun koodu
- [Iroyin Aabo Bandit](reports/bandit/index.md) - Awọn abajade iwadii aabo
- [Awọn Ipele Oṣuwọn](reports/benchmarks/index.md) - Awọn abajade ipele oṣuwọn

## E dupe

- Apejuwe protocol BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocol Xet fun imoran chunking ti a ṣe alaye nipasẹ akoonu
- Python asyncio fun I/O oṣuwọn giga
- Agbegbe BitTorrent fun idagbasoke protocol
































































































































































































