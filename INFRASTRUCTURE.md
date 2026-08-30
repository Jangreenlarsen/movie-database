# Portal-infrastruktur — `movie.laces.dk`

Nuværende opbygning af produktionsmiljøet for Film- & TV-database-portalen.
Beskriver **hvordan det ser ud i dag** — ingen historik.

> Konkrete IP-adresser, subnet og VLAN-id er bevidst udeladt her. De står i den
> git-ignorerede drifts-runbook sammen med adgangsoplysningerne.

---

## 1. Overblik

```
                 Internet
                    │  https://movie.laces.dk (TCP 443)
                    ▼
        ┌───────────────────────────┐
        │  Perimeter-firewall       │   ACL på indgående 80/443
        │                           │   DNAT/port-forward → proxyen
        └───────────┬───────────────┘
                    ▼
        ┌───────────────────────────────────────────┐
        │  nginx reverse proxy (VM)                 │
        │   • NIC 1: management + default route     │
        │   • NIC 2: transport-subnet mod appserver │
        │                                           │
        │   • TLS-terminering, Let's Encrypt-cert   │
        │   • proxy_pass → appserver :443           │
        │   • NAT/masquerade for appsegmentet       │
        └───────────┬───────────────────────────────┘
                    │  transport-subnet (dedikeret VLAN, L2-direkte)
                    ▼
        ┌───────────────────────────────────────────┐
        │  Appserver (Debian, VM)                   │
        │                                           │
        │  Caddy :443  ──► /api/*  → localhost:8000 │  FastAPI (uvicorn)
        │              └─► /*      → statiske filer │  React/Vite build
        │                                           │
        │  MongoDB     localhost:27017              │
        └───────────────────────────────────────────┘
```

---

## 2. Lagene, ét ad gangen

### Perimeter-firewall
Eneste vej ind fra internettet. ACL tillader TCP 80 og 443 mod portalens
offentlige adresse og NAT'er dem videre til nginx-proxyens management-interface.
Alt andet — SSH, database, backend — er lukket udefra. DNS-A-record for
`movie.laces.dk` peger på den offentlige adresse.

### nginx reverse proxy
Dedikeret VM med to aktive interfaces og to roller:

| Interface | Rolle |
|---|---|
| Management-NIC | Default route ud mod internettet, administration |
| Transport-NIC | L2-direkte forbindelse til appserverens segment; proxyen holder gateway-adressen |

1. **Reverse proxy / TLS-terminering** — tager imod den offentlige HTTPS-session,
   terminerer Let's Encrypt-certifikatet (certbot, automatisk fornyelse) og åbner
   en **ny** HTTPS-session mod appserverens `:443` med `Host: movie.laces.dk`.
   `proxy_http_version 1.1` + `proxy_buffering off` er sat, så streaming-svar
   (SSE) når klienten løbende i stedet for at blive bufferet.
2. **NAT-gateway for appsegmentet** — proxyens transport-NIC er default gateway
   for appserveren, og udgående trafik masquerades ud via management-NIC'et
   (nftables). Segmentet har bevidst ingen router-SVI: proxyen *er* gatewayen.

Konsekvens: falder proxyen ud, mister appserveren både indgående **og**
udgående forbindelse.

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

## 3. To TLS-hops, ikke passthrough

Trafikken dekrypteres og krypteres igen undervejs:

| Hop | Certifikat | Termineres af |
|---|---|---|
| Klient → proxy | Let's Encrypt (offentligt betroet) | nginx |
| Proxy → appserver | Caddys eget interne certifikat | Caddy |

Andet hop løber udelukkende i transport-subnettet. Proxyen validerer ikke
appserverens certifikat — det er transportkryptering på et lukket segment, ikke
en tillidskæde.

---

## 4. Trafikstrømme

| Retning | Vej |
|---|---|
| Klient → portal | Internet → firewall (ACL+DNAT) → nginx:443 → Caddy:443 → frontend/backend |
| Backend → eksterne API'er (TMDb, UPC, m.fl.) | Appserver → proxyens transport-NIC → NAT → internet |
| Drift/SSH | Kun fra transport-subnettet, i praksis via proxyen |

---

## 5. Ved ændringer — husk alle lag

Et nyt hostnavn eller en ny adgangsvej skal tilføjes **tre** steder for at virke
hele vejen igennem:

1. DNS + ACL/port-forward på perimeter-firewallen
2. nginx `server_name` (+ certifikat) på proxyen
3. Caddys site-blok på appserveren **og** backendens `CORS_ORIGINS`

Caddy matcher på HTTP `Host`-headeren: mangler navnet i site-blokken, svarer den
tomt `200 OK` selvom netværk og proxy er korrekte.
