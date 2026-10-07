# ChallengeLab – pre-DB01 snapshot

Dit repository bevat de ChallengeLab-configuratie van **WEB01 (192.168.10.22)** en **DOCKER01 (192.168.10.23)** zoals die werkte **voordat DB01/PostgreSQL werd toegevoegd**.

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

Nginx op WEB01 stuurt deze door naar Traefik op DOCKER01. Traefik ontdekt dynamisch de actieve challengecontainer via Docker-labels.

## Mappen

- `web01/` – FastAPI, Nginx, systemd en portal.
- `docker01/` – Traefik-configuratie en challenge-images.
- `ansible/` – basis deployment-notities.
- `docs/` – aanvullende configuratie-informatie.

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

Deze snapshot gebruikt nog de oorspronkelijke SQLite-sessieopslag in `/opt/challengelab/challengelab.db`.

## Belangrijke paden

### WEB01

```text
/opt/challengelab/main.py
/opt/challengelab/venv/
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

> Dit is een reconstructie van de werkende configuratie uit de bouwsessie vóór de DB01-migratie.
