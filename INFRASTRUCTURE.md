# Portal-infrastruktur — `movie.laces.dk`

Nuværende opbygning af produktionsmiljøet for Film- & TV-database-portalen.
Beskriver **hvordan det ser ud i dag** — ingen historik.

> Konkrete IP-adresser, subnet og VLAN-id er bevidst udeladt her. De står i den
> git-ignorerede drifts-runbook sammen med adgangsoplysningerne.

---

## 1. Overblik

Firewallen er navet. Den har tre ben: internettet, DMZ-subnettet og
transport-vejen ind til de to VM'er.

```
  INTERNET                                SYNOLOGY VMM — begge gæster Debian
  ┌────────────────────┐                ┌──────────────────────────────────────┐
  │ Klient · browser   │──── :443 ────┐ │  nginx reverse proxy (VM)            │
  ├────────────────────┤              │ │   • Management-NIC · default route   │
  │ Eksterne tjenester │              ├─┼──▶• nginx — TLS-terminering          │
  │  TMDb   OMDb/IMDb  │◀─ udgående ──┘ │   • Transport-NIC · gateway          │
  │  EAN-Search        │              │ │              │                       │
  │  UPCitemdb         │              │ │              ▼ transport-subnet      │
  │  UPCdatabase       │              │ │  ┌────────────────────────────────┐  │
  │  Discogs           │              │ │  │ Appserver (VM)                 │  │
  │  Resend · e-mail   │              │ │  │  Caddy :443                    │  │
  └────────────────────┘              │ │  │   ├─ /api/*  → FastAPI (lokal) │  │
             │                        │ │  │   └─ /*      → statiske filer  │  │
             │                        │ │  │  MongoDB (lokal)               │  │
  ┌──────────┴─────────┐              │ │  └────────────────────────────────┘  │
  │ Perimeter-firewall │──────────────┘ └──────────────────────────────────────┘
  │ ACL 80/443 · DNAT  │
  │ stateful           │      - - - udgående fra appserveren, NAT'et af proxyen
  └──────────┬─────────┘      ◀──▶ symmetrisk: retur følger samme vej
             │ DMZ-ben
  ┌──────────┴─────────┐
  │ DMZ-subnet         │
  │  Intern DNS-server │
  │  Plex-server       │
  │  Anthem AVM70      │
  └────────────────────┘
```

---

## 2. Lagene, ét ad gangen

### Virtualisering
Både proxyen og appserveren er **Debian-VM'er under Synology Virtual Machine
Manager**. De er netværksmæssigt adskilt, men deler hypervisor — et kendt fælles
fejlpunkt, ikke en netværkssvaghed.

### Perimeter-firewall
Eneste vej ind fra internettet, og navet for alle andre zoner. ACL tillader TCP
80 og 443 mod portalens offentlige adresse og NAT'er dem videre til
nginx-proxyens management-interface. Alt andet — SSH, database, backend — er
lukket udefra. DNS-A-record for `movie.laces.dk` peger på den offentlige adresse.

Firewallen er stateful, og al trafik gennem den er **symmetrisk** (se afsnit 3).
Ud over internet-benet og vejen ind til VM'erne har den et **DMZ-ben** mod et
internt subnet (se afsnit 4).

### nginx reverse proxy
Debian-VM med to aktive interfaces og to roller:

| Interface | Rolle |
|---|---|
| Management-NIC | Default route mod firewallen, administration, certifikat-fornyelse |
| Transport-NIC | L2-direkte mod appserverens segment; holder gateway-adressen |

1. **Reverse proxy / TLS-terminering** — tager imod den offentlige HTTPS-session,
   terminerer Let's Encrypt-certifikatet (certbot, automatisk fornyelse) og åbner
   en **ny** HTTPS-session mod appserverens `:443` med `Host: movie.laces.dk`.
   `proxy_http_version 1.1` + `proxy_buffering off` er sat, så streaming-svar
   (SSE) når klienten løbende i stedet for at blive bufferet.
2. **NAT-gateway for appsegmentet** — proxyens transport-NIC er default gateway
   for appserveren, og udgående trafik masquerades ud via management-NIC'et
   (nftables). Segmentet har bevidst ingen router-SVI: proxyen *er* gatewayen.

Konsekvens: falder proxyen ud, mister appserveren både indgående **og** udgående
forbindelse — inklusive navneopslag, Plex og AVM70.

### Transport-subnet
Isoleret L2-segment mellem proxy og appserver på et dedikeret VLAN. Ingen andre
routede veje ind i det — al klienttrafik kommer via proxyen, og SSH til
appserveren er begrænset til dette segment.

### Appserver
Debian-VM, alt kører native under systemd (ingen containere).

| Service | Bind | Rolle |
|---|---|---|
| Caddy | `0.0.0.0:80`, `0.0.0.0:443` | Reverse proxy + statisk fileserver |
| FastAPI (uvicorn) | `127.0.0.1:8000` | Backend-API |
| MongoDB | `127.0.0.1:27017` | Database |

Caddy er portalens interne indgang og deler trafikken:

* `/api/*` → `reverse_proxy 127.0.0.1:8000` (backend)
* alt andet → statiske filer fra frontend-buildet, med SPA-fallback til
  `index.html`

Backend og database lytter **kun** på loopback og kan ikke nås direkte fra
netværket. Lokal ufw: default-deny ind, 80/443 åbne, SSH kun fra
transport-subnettet. Caddy kører h1/h2 — HTTP/3 (QUIC/UDP) er slået fra, da kun
TCP 443 er åbnet.

---

## 3. Symmetrisk routing

Al trafik forlader miljøet ad samme vej som den kom ind — der er ingen
asymmetriske stier i opsætningen:

* **Indgående klienttrafik** returneres gennem den firewall den kom ind ad.
* **Udgående trafik fra appserveren** (eksterne API'er, DMZ-tjenester,
  navneopslag, pakkeopdateringer) går til proxyens transport-NIC, NAT'es ud via
  management-NIC'et og videre gennem firewallen — svaret følger samme kæde retur.
* **Udgående trafik fra proxyen selv** går direkte ud via management-NIC'et
  gennem firewallen, med samme symmetriske retur.

Det er en forudsætning, ikke en tilfældighed: firewallen er stateful, og en
asymmetrisk retursti ville få den til at droppe svarpakker på en forbindelse den
ikke selv har set etableret.

---

## 4. DMZ-subnettet

Firewallens tredje ben. Alt herpå nås fra appserveren via proxyens NAT og gennem
firewallen — aldrig direkte, da appserverens segment ikke har anden vej ud.

| Vært | Port | Bruges af | Formål |
|---|---|---|---|
| Intern DNS-server | 53 | Begge VM'er | Alle navneopslag. Der bruges ingen offentlige resolvere direkte fra VM'erne |
| Plex-server | `:32400` | Backend | Import af eksisterende bibliotek |
| Anthem AVM70 | TCP `14999` | Backend | Styring og diagnostik af receiveren |

Praktisk konsekvens for DNS: skal et navn kunne slås op *indefra*, skal recorden
også findes i den interne DNS — den offentlige DNS-record alene er ikke nok.

---

## 5. Eksterne tjenester på internettet

Al udgående integration initieres af backend'en på appserveren, over HTTPS,
gennem proxyens NAT og firewallens internet-ben.

| Tjeneste | Formål |
|---|---|
| TMDb | Film- og TV-metadata samt posters |
| OMDb | IMDb-data |
| EAN-Search | Stregkode-opslag (UPC/EAN) |
| UPCitemdb | Stregkode-opslag (UPC/EAN) |
| UPCdatabase | Stregkode-opslag (UPC/EAN) |
| Discogs | Musik-metadata |
| Resend | Udgående e-mail, fx nulstilling af adgangskode |

Frontend kalder aldrig disse direkte — kun backend'ens eget REST API, jf.
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## 6. To TLS-hops, ikke passthrough

Trafikken dekrypteres og krypteres igen undervejs:

| Hop | Certifikat | Termineres af |
|---|---|---|
| Klient → proxy | Let's Encrypt (offentligt betroet) | nginx |
| Proxy → appserver | Caddys eget interne certifikat | Caddy |

Andet hop løber udelukkende i transport-subnettet. Proxyen validerer ikke
appserverens certifikat — det er transportkryptering på et lukket segment, ikke
en tillidskæde.

---

## 7. Trafikstrømme

| Retning | Vej |
|---|---|
| Klient → portal | Internet → firewall (ACL+DNAT) → nginx:443 → Caddy:443 → frontend/backend |
| Backend → eksterne API'er | Appserver → transport-NIC → NAT → firewall → internet |
| Backend → Plex / AVM70 | Appserver → transport-NIC → NAT → firewall → DMZ-ben |
| Navneopslag (begge VM'er) | → firewall → DMZ-ben → intern DNS-server |
| Drift/SSH | Kun fra transport-subnettet, i praksis via proxyen |

Alle rækker returnerer ad samme vej, jf. afsnit 3.

---

## 8. Ved ændringer — husk alle lag

Et nyt hostnavn eller en ny adgangsvej skal tilføjes **fire** steder for at virke
hele vejen igennem:

1. Offentlig DNS + ACL/port-forward på perimeter-firewallen
2. Intern DNS på DMZ-subnettet, hvis navnet også skal kunne slås op indefra
3. nginx `server_name` (+ certifikat) på proxyen
4. Caddys site-blok på appserveren **og** backendens `CORS_ORIGINS`

Caddy matcher på HTTP `Host`-headeren: mangler navnet i site-blokken, svarer den
tomt `200 OK` selvom netværk og proxy er korrekte.
