# ccBitTorrent - Mteja wa BitTorrent wa Utendaji wa Juu

Mteja wa BitTorrent wa kisasa na utendaji wa juu uliojengwa na Python asyncio, ukiwa na algorithms za hali ya juu za uchaguzi wa vipande, ubadilishanaji wa metadata sambamba, na I/O ya diski iliyoboreshwa.

## Vipengele

### Uboreshaji wa Utendaji
- **Async I/O**: Utekelezaji kamili wa asyncio kwa ushirikiano bora zaidi
- **Uchaguzi wa Rarest-First**: Uchaguzi wa akili wa vipande kwa afya bora ya swarm
- **Hali ya Endgame**: Maombi yanayorudiwa kwa kukamilika kwa haraka
- **Pipeline ya Maombi**: Foleni za maombi za kina (16-64 maombi yasiyokamilika kwa kila peer)
- **Tit-for-Tat Choking**: Mgawanyo wa haki wa bandwidth na optimistic unchoke
- **Metadata Sambamba**: Upatikanaji wa ut_metadata sambamba kutoka kwa peers nyingi
- **Uboreshaji wa Disk I/O**: Uwekaji awali wa faili, uandikaji kwa makundi, ring-buffer staging, memory-mapped I/O
- **Pool ya Uthibitishaji wa Hash**: Uthibitishaji wa SHA-1 sambamba katika threads za wafanyakazi

### Mipangilio ya Hali ya Juu
- **Mipangilio ya TOML**: Mfumo kamili wa mpangilio na upakiaji tena wa joto
- **Mipangilio ya Kila Torrent**: Uvunjaji wa mpangilio wa torrent binafsi
- **Kikomo cha Kasi**: Mipaka ya dunia na ya kila torrent ya upload/download
- **Uchaguzi wa Mkakati**: Uchaguzi wa vipande round-robin, rarest-first, au mfululizo
- **Hali ya Streaming**: Uchaguzi wa vipande unaotegemea kipaumbele kwa faili za multimedia

### Vipengele vya Mtandao
- **Msaada wa UDP Tracker**: Mawasiliano ya tracker UDP inayofuata BEP 15
- **DHT Iliyoboreshwa**: Jedwali kamili la routing la Kademlia na utafutaji unaorudiwa
- **Ubadilishanaji wa Peer (PEX)**: Ugunduzi wa peer unaofuata BEP 11
- **Usimamizi wa Muunganisho**: Uchaguzi wa peer unaojifunza na mipaka ya muunganisho
- **Uboreshaji wa Itifaki**: Usimamizi wa ufanisi wa kumbukumbu wa ujumbe na njia za sifuri-nakili

## Upanuzi wa Itifaki ya Xet (BEP XET)

Upanuzi wa Itifaki ya Xet ni tofauti muhimu inayobadilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer wa haraka sana, unaoweza kusasishwa ulioongezwa kwa ushirikiano. BEP XET huruhusu:

- **Chunking Inayofafanuliwa na Maudhui**: Umgawanyo wa akili wa faili unaotegemea Gearhash (chunks 8KB-128KB) kwa usasishaji ufanisi
- **Deduplication Kati ya Torrent**: Deduplication ya kiwango cha chunk kati ya torrents nyingi
- **CAS Peer-to-Peer**: Hifadhi ya Maudhui Inayoweza Kuanzishwa Isiyo na Kituo kwa kutumia DHT na trackers
- **Usasishaji wa Haraka Sana**: Chunks zilizobadilishwa tu zinahitaji kusambazwa tena, kuwezesha ushirikiano wa haraka wa faili za ushirikiano
- **Mfumo wa Faili wa P2P**: Badilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer unaoweza kusasishwa ulioongezwa kwa ushirikiano
- **Uthibitishaji wa Mti wa Merkle**: Hashing BLAKE3-256 na fallback SHA-256 kwa uadilifu

[Jifunze zaidi kuhusu BEP XET →](bep_xet.md)

## Anza Haraka

### Ufungaji na UV

Funga UV kutoka [astral.sh/uv](https://astral.sh/uv), kisha funga ccBitTorrent.

### Sehemu Kuu za Kuingia

**Bitonic** - Interface kuu ya dashboard ya terminal (inapendekezwa):
- Anzisha: `uv run bitonic` au `uv run ccbt dashboard`

**btbt CLI** - Interface iliyoboreshwa ya mstari wa amri:
- Anzisha: `uv run btbt`

**ccbt** - Interface ya msingi ya CLI:
- Anzisha: `uv run ccbt`

Kwa matumizi ya kina, angalia:
- [Mwongozo wa Kuanza](getting-started.md) - Mafunzo hatua kwa hatua
- [Bitonic](bitonic.md) - Mwongozo wa dashboard ya terminal
- [btbt CLI](btbt-cli.md) - Rejea kamili ya amri

## Hati

- [BEP XET](bep_xet.md) - Upanuzi wa Itifaki ya Xet kwa chunking inayofafanuliwa na maudhui na deduplication
- [Kuanza](getting-started.md) - Ufungaji na hatua za kwanza
- [Bitonic](bitonic.md) - Dashboard ya terminal (interface kuu)
- [btbt CLI](btbt-cli.md) - Rejea ya interface ya mstari wa amri
- [Mipangilio](configuration.md) - Chaguzi za mpangilio na usanidi
- [Uboreshaji wa Utendaji](performance.md) - Mwongozo wa uboreshaji
- [Rejea ya API ya ccBT](API.md) - Hati za API za Python
- [Kuchangia](contributing.md) - Jinsi ya kuchangia
- [Ufadhili](funding.md) - Msaada wa mradi

## Leseni

Mradi huu umepewa leseni chini ya **GNU General Public License v2 (GPL-2.0)** - angalia [license.md](license.md) kwa maelezo.

Zaidi ya hayo, mradi huu unashikiliwa na vikwazo vya ziada vya matumizi chini ya **Leseni ya ccBT RAIL-AMS** - angalia [ccBT-RAIL.md](ccBT-RAIL.md) kwa masharti kamili na vikwazo vya matumizi.

**Muhimu**: Leseni zote mbili zinatumika kwa programu hii. Lazima uzingatie masharti yote na vikwazo katika leseni ya GPL-2.0 na leseni ya RAIL.

## Ripoti

Angalia ripoti za mradi katika hati:
- [Ripoti za Ufuniko](reports/coverage.md) - Uchambuzi wa ufuniko wa msimbo
- [Ripoti ya Usalama ya Bandit](reports/bandit/index.md) - Matokeo ya uchunguzi wa usalama
- [Vipimo vya Utendaji](reports/benchmarks/index.md) - Matokeo ya vipimo vya utendaji

## Shukrani

- Uainishaji wa itifaki ya BitTorrent (BEP 5, 10, 11, 15, 52)
- Itifaki ya Xet kwa msukumo wa chunking inayofafanuliwa na maudhui
- Python asyncio kwa I/O ya utendaji wa juu
- Jumuiya ya BitTorrent kwa maendeleo ya itifaki






Mteja wa BitTorrent wa kisasa na utendaji wa juu uliojengwa na Python asyncio, ukiwa na algorithms za hali ya juu za uchaguzi wa vipande, ubadilishanaji wa metadata sambamba, na I/O ya diski iliyoboreshwa.

## Vipengele

### Uboreshaji wa Utendaji
- **Async I/O**: Utekelezaji kamili wa asyncio kwa ushirikiano bora zaidi
- **Uchaguzi wa Rarest-First**: Uchaguzi wa akili wa vipande kwa afya bora ya swarm
- **Hali ya Endgame**: Maombi yanayorudiwa kwa kukamilika kwa haraka
- **Pipeline ya Maombi**: Foleni za maombi za kina (16-64 maombi yasiyokamilika kwa kila peer)
- **Tit-for-Tat Choking**: Mgawanyo wa haki wa bandwidth na optimistic unchoke
- **Metadata Sambamba**: Upatikanaji wa ut_metadata sambamba kutoka kwa peers nyingi
- **Uboreshaji wa Disk I/O**: Uwekaji awali wa faili, uandikaji kwa makundi, ring-buffer staging, memory-mapped I/O
- **Pool ya Uthibitishaji wa Hash**: Uthibitishaji wa SHA-1 sambamba katika threads za wafanyakazi

### Mipangilio ya Hali ya Juu
- **Mipangilio ya TOML**: Mfumo kamili wa mpangilio na upakiaji tena wa joto
- **Mipangilio ya Kila Torrent**: Uvunjaji wa mpangilio wa torrent binafsi
- **Kikomo cha Kasi**: Mipaka ya dunia na ya kila torrent ya upload/download
- **Uchaguzi wa Mkakati**: Uchaguzi wa vipande round-robin, rarest-first, au mfululizo
- **Hali ya Streaming**: Uchaguzi wa vipande unaotegemea kipaumbele kwa faili za multimedia

### Vipengele vya Mtandao
- **Msaada wa UDP Tracker**: Mawasiliano ya tracker UDP inayofuata BEP 15
- **DHT Iliyoboreshwa**: Jedwali kamili la routing la Kademlia na utafutaji unaorudiwa
- **Ubadilishanaji wa Peer (PEX)**: Ugunduzi wa peer unaofuata BEP 11
- **Usimamizi wa Muunganisho**: Uchaguzi wa peer unaojifunza na mipaka ya muunganisho
- **Uboreshaji wa Itifaki**: Usimamizi wa ufanisi wa kumbukumbu wa ujumbe na njia za sifuri-nakili

## Upanuzi wa Itifaki ya Xet (BEP XET)

Upanuzi wa Itifaki ya Xet ni tofauti muhimu inayobadilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer wa haraka sana, unaoweza kusasishwa ulioongezwa kwa ushirikiano. BEP XET huruhusu:

- **Chunking Inayofafanuliwa na Maudhui**: Umgawanyo wa akili wa faili unaotegemea Gearhash (chunks 8KB-128KB) kwa usasishaji ufanisi
- **Deduplication Kati ya Torrent**: Deduplication ya kiwango cha chunk kati ya torrents nyingi
- **CAS Peer-to-Peer**: Hifadhi ya Maudhui Inayoweza Kuanzishwa Isiyo na Kituo kwa kutumia DHT na trackers
- **Usasishaji wa Haraka Sana**: Chunks zilizobadilishwa tu zinahitaji kusambazwa tena, kuwezesha ushirikiano wa haraka wa faili za ushirikiano
- **Mfumo wa Faili wa P2P**: Badilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer unaoweza kusasishwa ulioongezwa kwa ushirikiano
- **Uthibitishaji wa Mti wa Merkle**: Hashing BLAKE3-256 na fallback SHA-256 kwa uadilifu

[Jifunze zaidi kuhusu BEP XET →](bep_xet.md)

## Anza Haraka

### Ufungaji na UV

Funga UV kutoka [astral.sh/uv](https://astral.sh/uv), kisha funga ccBitTorrent.

### Sehemu Kuu za Kuingia

**Bitonic** - Interface kuu ya dashboard ya terminal (inapendekezwa):
- Anzisha: `uv run bitonic` au `uv run ccbt dashboard`

**btbt CLI** - Interface iliyoboreshwa ya mstari wa amri:
- Anzisha: `uv run btbt`

**ccbt** - Interface ya msingi ya CLI:
- Anzisha: `uv run ccbt`

Kwa matumizi ya kina, angalia:
- [Mwongozo wa Kuanza](getting-started.md) - Mafunzo hatua kwa hatua
- [Bitonic](bitonic.md) - Mwongozo wa dashboard ya terminal
- [btbt CLI](btbt-cli.md) - Rejea kamili ya amri

## Hati

- [BEP XET](bep_xet.md) - Upanuzi wa Itifaki ya Xet kwa chunking inayofafanuliwa na maudhui na deduplication
- [Kuanza](getting-started.md) - Ufungaji na hatua za kwanza
- [Bitonic](bitonic.md) - Dashboard ya terminal (interface kuu)
- [btbt CLI](btbt-cli.md) - Rejea ya interface ya mstari wa amri
- [Mipangilio](configuration.md) - Chaguzi za mpangilio na usanidi
- [Uboreshaji wa Utendaji](performance.md) - Mwongozo wa uboreshaji
- [Rejea ya API ya ccBT](API.md) - Hati za API za Python
- [Kuchangia](contributing.md) - Jinsi ya kuchangia
- [Ufadhili](funding.md) - Msaada wa mradi

## Leseni

Mradi huu umepewa leseni chini ya **GNU General Public License v2 (GPL-2.0)** - angalia [license.md](license.md) kwa maelezo.

Zaidi ya hayo, mradi huu unashikiliwa na vikwazo vya ziada vya matumizi chini ya **Leseni ya ccBT RAIL-AMS** - angalia [ccBT-RAIL.md](ccBT-RAIL.md) kwa masharti kamili na vikwazo vya matumizi.

**Muhimu**: Leseni zote mbili zinatumika kwa programu hii. Lazima uzingatie masharti yote na vikwazo katika leseni ya GPL-2.0 na leseni ya RAIL.

## Ripoti

Angalia ripoti za mradi katika hati:
- [Ripoti za Ufuniko](reports/coverage.md) - Uchambuzi wa ufuniko wa msimbo
- [Ripoti ya Usalama ya Bandit](reports/bandit/index.md) - Matokeo ya uchunguzi wa usalama
- [Vipimo vya Utendaji](reports/benchmarks/index.md) - Matokeo ya vipimo vya utendaji

## Shukrani

- Uainishaji wa itifaki ya BitTorrent (BEP 5, 10, 11, 15, 52)
- Itifaki ya Xet kwa msukumo wa chunking inayofafanuliwa na maudhui
- Python asyncio kwa I/O ya utendaji wa juu
- Jumuiya ya BitTorrent kwa maendeleo ya itifaki
































































































































































































