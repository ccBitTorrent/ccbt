# ccBitTorrent - Mai Kwalwalwar BitTorrent Client

Mai kwalwalwar BitTorrent client na zamani wanda aka gina tare da Python asyncio, yana da manyan algorithms na zaɓin guntu, musayar metadata na layi daya, da ingantaccen disk I/O.

## Siffofi

### Ingantattun Ayyuka
- **Async I/O**: Cikakken aiwatarwa na asyncio don haɗin kai mafi girma
- **Zaɓin Rarest-First**: Zaɓin guntu mai hankali don lafiyar swarm mafi kyau
- **Yanayin Endgame**: Buƙatun kwafi don kammalawa mai sauri
- **Pipeline na Buƙatu**: Layukan buƙatu masu zurfi (16-64 buƙatu masu tsaye a kowane peer)
- **Tit-for-Tat Choking**: Rarraba bandwidth na gaskiya tare da optimistic unchoke
- **Metadata na Layi daya**: Samun ut_metadata na layi daya daga peers da yawa
- **Ingantaccen Disk I/O**: Fara shirya fayil, rubutu a cikin rukuni, ring-buffer staging, memory-mapped I/O
- **Tafkin Tabbatar da Hash**: Tabbatar da SHA-1 na layi daya a cikin ma'aikatan threads

### Saituna na Ci gaba
- **Saitunan TOML**: Cikakken tsarin saiti tare da sake lodawa mai zafi
- **Saituna na Kowane Torrent**: Sauye-sauyen saiti na kowane torrent
- **Iyakancewar Ƙimar**: Iyakoki na duniya da na kowane torrent na upload/download
- **Zaɓin Dabarar**: Zaɓin guntu round-robin, rarest-first, ko na jeri
- **Yanayin Streaming**: Zaɓin guntu bisa fifiko don fayilolin multimedia

### Siffofi na Network
- **Tallafi na UDP Tracker**: Sadarwar tracker UDP mai bin BEP 15
- **DHT mai Ingantawa**: Cikakken tebur na routing na Kademlia tare da bincike masu maimaitawa
- **Musayar Peer (PEX)**: Gano peer mai bin BEP 11
- **Gudanar da Haɗin kai**: Zaɓin peer mai daidaitawa da iyakoki na haɗin kai
- **Ingantattun Protocol**: Gudanar da saƙo mai amfani da ƙwaƙwalwa tare da hanyoyi marasa kwafi

## Ƙari na Protocol Xet (BEP XET)

Ƙari na Protocol Xet shine abin da ya bambanta wanda ke canza BitTorrent zuwa tsarin fayil na peer-to-peer mai sauri, mai sabuntawa wanda aka inganta don haɗin gwiwa. BEP XET yana ba da damar:

- **Chunking da aka Ayyana ta Content**: Rarraba fayil mai hankali bisa Gearhash (chunks 8KB-128KB) don sabuntawa mai inganci
- **Deduplication tsakanin Torrent**: Deduplication na matakin chunk tsakanin torrents da yawa
- **CAS Peer-to-Peer**: Ajiya ta Content Addressable mara tsakiya ta amfani da DHT da trackers
- **Sabuntawa masu Sauri**: Chunks da aka canza kawai suna buƙatar sake rarraba, yana ba da damar raba fayil mai sauri na haɗin gwiwa
- **Tsarin Fayil na P2P**: Canza BitTorrent zuwa tsarin fayil na peer-to-peer mai sabuntawa wanda aka inganta don haɗin gwiwa
- **Tabbatar da Bishiyar Merkle**: Hashing BLAKE3-256 tare da fallback SHA-256 don gaskiya

[Koyi ƙarin game da BEP XET →](bep_xet.md)

## Fara da Sauri

### Shigarwa tare da UV

Shigar UV daga [astral.sh/uv](https://astral.sh/uv), sannan shigar ccBitTorrent.

### Manyan Wuraren Shiga

**Bitonic** - Babban interface na dashboard na terminal (ana ba da shawara):
- Fara: `uv run bitonic` ko `uv run ccbt dashboard`

**btbt CLI** - Ingantaccen interface na layin umarni:
- Fara: `uv run btbt`

**ccbt** - Interface na CLI na asali:
- Fara: `uv run ccbt`

Don cikakken amfani, duba:
- [Jagorar Fara](getting-started.md) - Tutorial mataki-mataki
- [Bitonic](bitonic.md) - Jagorar dashboard na terminal
- [btbt CLI](btbt-cli.md) - Cikakken nassoshi na umarni

## Takardu

- [BEP XET](bep_xet.md) - Ƙari na Protocol Xet don chunking da aka ayyana ta content da deduplication
- [Fara](getting-started.md) - Shigarwa da matakan farko
- [Bitonic](bitonic.md) - Dashboard na terminal (babban interface)
- [btbt CLI](btbt-cli.md) - Nassoshi na interface na layin umarni
- [Saituna](configuration.md) - Zaɓuɓɓukan saiti da saitin
- [Daidaituwar Aiki](performance.md) - Jagorar ingantawa
- [Nassoshi na API ccBT](API.md) - Takardun API na Python
- [Ba da gudummawa](contributing.md) - Yadda ake ba da gudummawa
- [Kudade](funding.md) - Taimaka wa aikin

## Lasisi

Wannan aikin yana ƙarƙashin **GNU General Public License v2 (GPL-2.0)** - duba [license.md](license.md) don cikakkun bayanai.

Bugu da ƙari, wannan aikin yana ƙarƙashin ƙarin hani na amfani a ƙarƙashin **Lasisi ccBT RAIL-AMS** - duba [ccBT-RAIL.md](ccBT-RAIL.md) don cikakkun sharuɗɗa da hani na amfani.

**Mahimmanci**: Dukansu lasisoshi suna aiki akan wannan software. Dole ne ku bi duk sharuɗɗa da hani a cikin lasisin GPL-2.0 da lasisin RAIL.

## Rahotanni

Duba rahotannin aikin a cikin takardu:
- [Rahotannin Rufe](reports/coverage.md) - Binciken rufewa na code
- [Rahoton Tsaro na Bandit](reports/bandit/index.md) - Sakamakon binciken tsaro
- [Benchmarks](reports/benchmarks/index.md) - Sakamakon benchmark na aiki

## Godiya

- Ƙayyadaddun protocol na BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocol Xet don wahayi na chunking da aka ayyana ta content
- Python asyncio don I/O mai ƙarfi
- Al'ummar BitTorrent don haɓaka protocol






Mai kwalwalwar BitTorrent client na zamani wanda aka gina tare da Python asyncio, yana da manyan algorithms na zaɓin guntu, musayar metadata na layi daya, da ingantaccen disk I/O.

## Siffofi

### Ingantattun Ayyuka
- **Async I/O**: Cikakken aiwatarwa na asyncio don haɗin kai mafi girma
- **Zaɓin Rarest-First**: Zaɓin guntu mai hankali don lafiyar swarm mafi kyau
- **Yanayin Endgame**: Buƙatun kwafi don kammalawa mai sauri
- **Pipeline na Buƙatu**: Layukan buƙatu masu zurfi (16-64 buƙatu masu tsaye a kowane peer)
- **Tit-for-Tat Choking**: Rarraba bandwidth na gaskiya tare da optimistic unchoke
- **Metadata na Layi daya**: Samun ut_metadata na layi daya daga peers da yawa
- **Ingantaccen Disk I/O**: Fara shirya fayil, rubutu a cikin rukuni, ring-buffer staging, memory-mapped I/O
- **Tafkin Tabbatar da Hash**: Tabbatar da SHA-1 na layi daya a cikin ma'aikatan threads

### Saituna na Ci gaba
- **Saitunan TOML**: Cikakken tsarin saiti tare da sake lodawa mai zafi
- **Saituna na Kowane Torrent**: Sauye-sauyen saiti na kowane torrent
- **Iyakancewar Ƙimar**: Iyakoki na duniya da na kowane torrent na upload/download
- **Zaɓin Dabarar**: Zaɓin guntu round-robin, rarest-first, ko na jeri
- **Yanayin Streaming**: Zaɓin guntu bisa fifiko don fayilolin multimedia

### Siffofi na Network
- **Tallafi na UDP Tracker**: Sadarwar tracker UDP mai bin BEP 15
- **DHT mai Ingantawa**: Cikakken tebur na routing na Kademlia tare da bincike masu maimaitawa
- **Musayar Peer (PEX)**: Gano peer mai bin BEP 11
- **Gudanar da Haɗin kai**: Zaɓin peer mai daidaitawa da iyakoki na haɗin kai
- **Ingantattun Protocol**: Gudanar da saƙo mai amfani da ƙwaƙwalwa tare da hanyoyi marasa kwafi

## Ƙari na Protocol Xet (BEP XET)

Ƙari na Protocol Xet shine abin da ya bambanta wanda ke canza BitTorrent zuwa tsarin fayil na peer-to-peer mai sauri, mai sabuntawa wanda aka inganta don haɗin gwiwa. BEP XET yana ba da damar:

- **Chunking da aka Ayyana ta Content**: Rarraba fayil mai hankali bisa Gearhash (chunks 8KB-128KB) don sabuntawa mai inganci
- **Deduplication tsakanin Torrent**: Deduplication na matakin chunk tsakanin torrents da yawa
- **CAS Peer-to-Peer**: Ajiya ta Content Addressable mara tsakiya ta amfani da DHT da trackers
- **Sabuntawa masu Sauri**: Chunks da aka canza kawai suna buƙatar sake rarraba, yana ba da damar raba fayil mai sauri na haɗin gwiwa
- **Tsarin Fayil na P2P**: Canza BitTorrent zuwa tsarin fayil na peer-to-peer mai sabuntawa wanda aka inganta don haɗin gwiwa
- **Tabbatar da Bishiyar Merkle**: Hashing BLAKE3-256 tare da fallback SHA-256 don gaskiya

[Koyi ƙarin game da BEP XET →](bep_xet.md)

## Fara da Sauri

### Shigarwa tare da UV

Shigar UV daga [astral.sh/uv](https://astral.sh/uv), sannan shigar ccBitTorrent.

### Manyan Wuraren Shiga

**Bitonic** - Babban interface na dashboard na terminal (ana ba da shawara):
- Fara: `uv run bitonic` ko `uv run ccbt dashboard`

**btbt CLI** - Ingantaccen interface na layin umarni:
- Fara: `uv run btbt`

**ccbt** - Interface na CLI na asali:
- Fara: `uv run ccbt`

Don cikakken amfani, duba:
- [Jagorar Fara](getting-started.md) - Tutorial mataki-mataki
- [Bitonic](bitonic.md) - Jagorar dashboard na terminal
- [btbt CLI](btbt-cli.md) - Cikakken nassoshi na umarni

## Takardu

- [BEP XET](bep_xet.md) - Ƙari na Protocol Xet don chunking da aka ayyana ta content da deduplication
- [Fara](getting-started.md) - Shigarwa da matakan farko
- [Bitonic](bitonic.md) - Dashboard na terminal (babban interface)
- [btbt CLI](btbt-cli.md) - Nassoshi na interface na layin umarni
- [Saituna](configuration.md) - Zaɓuɓɓukan saiti da saitin
- [Daidaituwar Aiki](performance.md) - Jagorar ingantawa
- [Nassoshi na API ccBT](API.md) - Takardun API na Python
- [Ba da gudummawa](contributing.md) - Yadda ake ba da gudummawa
- [Kudade](funding.md) - Taimaka wa aikin

## Lasisi

Wannan aikin yana ƙarƙashin **GNU General Public License v2 (GPL-2.0)** - duba [license.md](license.md) don cikakkun bayanai.

Bugu da ƙari, wannan aikin yana ƙarƙashin ƙarin hani na amfani a ƙarƙashin **Lasisi ccBT RAIL-AMS** - duba [ccBT-RAIL.md](ccBT-RAIL.md) don cikakkun sharuɗɗa da hani na amfani.

**Mahimmanci**: Dukansu lasisoshi suna aiki akan wannan software. Dole ne ku bi duk sharuɗɗa da hani a cikin lasisin GPL-2.0 da lasisin RAIL.

## Rahotanni

Duba rahotannin aikin a cikin takardu:
- [Rahotannin Rufe](reports/coverage.md) - Binciken rufewa na code
- [Rahoton Tsaro na Bandit](reports/bandit/index.md) - Sakamakon binciken tsaro
- [Benchmarks](reports/benchmarks/index.md) - Sakamakon benchmark na aiki

## Godiya

- Ƙayyadaddun protocol na BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocol Xet don wahayi na chunking da aka ayyana ta content
- Python asyncio don I/O mai ƙarfi
- Al'ummar BitTorrent don haɓaka protocol
































































































































































































