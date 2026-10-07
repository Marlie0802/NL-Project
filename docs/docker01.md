# DOCKER01

**IP:** 192.168.10.23

DOCKER01 draait alle tijdelijke challenge-containers.

## Software

- Ubuntu Server
- Docker
- Traefik v3

## Docker gebruiker

De gebruiker `team` moet Docker kunnen gebruiken:

```bash
sudo usermod -aG docker team
```

Log daarna opnieuw in zodat het groepslidmaatschap actief wordt.

Test:

```bash
docker ps
```

## Challenge netwerk

```bash
docker network inspect challenge-net >/dev/null 2>&1 || docker network create challenge-net
```

Alle challengecontainers en Traefik zitten in dit netwerk.

## Traefik

Containernaam:

```text
challengelab-proxy
```

Hostpoort:

```text
8081 -> containerpoort 80
```

Startcommando staat ook onder `docker01/traefik/README.md`.

Controle:

```bash
docker ps --filter name=challengelab-proxy
curl -I http://192.168.10.23:8081
```

Een 404 op de root van Traefik is normaal als geen router voor `/` bestaat.

## Challenge broncode

```text
/home/team/challengelab/challenges/
```

Iedere challenge:

```text
challenge-id/
├── Dockerfile
└── html/
    └── index.html
```

Dockerfile:

```dockerfile
FROM nginx:alpine

COPY html/ /usr/share/nginx/html/

EXPOSE 80
```

Build:

```bash
cd /home/team/challengelab/challenges/<challenge-id>
docker build -t challengelab/<challenge-id>:1.0 .
```

## Handmatig testen

Een image kan zonder sessieflow worden getest:

```bash
docker run -d --name test-challenge -p 8090:80 challengelab/de-verkeerde-deur:1.0
```

Open:

```text
http://192.168.10.23:8090
```

Opruimen:

```bash
docker rm -f test-challenge
```

Let op: de knop Controleer op de challengepagina verwacht normaal een geldige ChallengeLab-session-ID en werkt in zo'n losse test dus niet volledig.
