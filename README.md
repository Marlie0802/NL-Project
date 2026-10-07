# ChallengeLab – pre-DB01 snapshot

Dit repository documenteert de ChallengeLab-configuratie van **WEB01 (192.168.10.22)** en **DOCKER01 (192.168.10.23)** zoals die werkte **vóór DB01/PostgreSQL werd toegevoegd**.

## Architectuur

```text
Browser
  |
  v
WEB01 - 192.168.10.22
  |- Nginx
  |- statische portal
  |- FastAPI / Uvicorn
  |- SQLite sessies
  |
  | SSH
  v
DOCKER01 - 192.168.10.23
  |- Docker
  |- challenge-net
  |- Traefik :8081
  |- 10 challenge-images
```

Challenge-routes lopen via WEB01:

```text
/c/<instance-id>/
```

Nginx stuurt deze door naar Traefik op DOCKER01. Traefik ontdekt actieve challengecontainers automatisch via Docker-labels.

## Documentatie

- [Architectuur](docs/architecture.md)
- [WEB01 configuratie](docs/web01.md)
- [DOCKER01 configuratie](docs/docker01.md)
- [API en sessieflow](docs/api.md)
- [Alle 10 challenges](docs/challenges.md)
- [Dagelijks beheer](docs/operations.md)
- [Testen en troubleshooting](docs/testing.md)
- [HTTPS-plan](docs/https.md)
- [Traefik](docker01/traefik/README.md)
- [Challenge image-opbouw](docker01/challenges/README.md)

## Configuratiebestanden

- `web01/app/main.py` – FastAPI pre-DB01 backend
- `web01/systemd/challengelab.service` – systemd service
- `web01/nginx/challenges` – Nginx reverse proxy
- `docker01/challenges/*/Dockerfile` – challenge images
- `ansible/inventory.example.ini` – voorbeeld inventory

## Challenges

1. De vergeten medewerker
2. De gebroken toegangscode
3. Bericht van Directeur
4. Wie kun je vertrouwen?
5. De verkeerde deur
6. De verboden route
7. De ontbrekende minuten
8. Wie was het?
9. Het geheime bericht
10. De echte Kluis

## Beveiliging

Bewust **niet** opgenomen:

- SSH private keys
- wachtwoorden
- `.env`-bestanden
- databasecredentials
- live sessiedata
- SQLite databasebestand

Deze snapshot gebruikt nog SQLite voor sessies:

```text
/opt/challengelab/challengelab.db
```

## Belangrijke serverpaden

### WEB01

```text
/opt/challengelab/main.py
/opt/challengelab/venv/
/opt/challengelab/challengelab.db
/etc/systemd/system/challengelab.service
/etc/nginx/sites-available/challenges
/var/www/challenges/index.html
/home/team/.ssh/challengelab_docker
```

### DOCKER01

```text
/home/team/challengelab/challenges/
/var/run/docker.sock
Docker network: challenge-net
Traefik container: challengelab-proxy
```

## Status van deze snapshot

Dit is een **gereconstrueerde technische snapshot** uit de werkende configuratie die we samen hebben gebouwd vóór de DB01-migratie. De serverarchitectuur, API-flow, Nginx, systemd, Traefik, challenge-opbouw, antwoorden, testprocedures en bekende fouten/fixes zijn vastgelegd.

De exacte actuele HTML-bestanden van alle challengepagina's kunnen alleen 1-op-1 uit DOCKER01 worden overgenomen als die serverbestanden rechtstreeks beschikbaar worden gemaakt; de documentatie beschrijft wel volledig hun werking en inhoud.
