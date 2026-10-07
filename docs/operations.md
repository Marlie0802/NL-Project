# Beheer van de pre-DB01 omgeving

## ChallengeLab herstarten

WEB01:

```bash
sudo systemctl restart challengelab
sudo systemctl reload nginx
```

DOCKER01 Traefik:

```bash
docker restart challengelab-proxy
```

## Actieve challengecontainers bekijken

```bash
docker ps --filter "name=challenge-"
```

Inclusief gestopte containers:

```bash
docker ps -a --filter "name=challenge-"
```

## Oude testcontainers verwijderen

Voorbeeld:

```bash
docker rm -f challenge-19cfee37 challenge-dd33a63b
```

Verwijder alleen containers waarvan je zeker weet dat ze niet meer bij een actieve sessie horen.

## Challenge aanpassen

Voorbeeld:

```bash
cd ~/challengelab/challenges/de-verkeerde-deur
nano html/index.html
docker build -t challengelab/de-verkeerde-deur:1.0 .
```

Een bestaande container blijft de oude image-laag gebruiken. Start dus een nieuwe sessie/instance om de wijziging te testen.

## Challenge los testen

```bash
docker run -d \
  --name test-challenge \
  -p 8090:80 \
  challengelab/de-verkeerde-deur:1.0
```

Na testen:

```bash
docker rm -f test-challenge
```

## Challengecatalogus wijzigen

Aanpassen in:

```text
/opt/challengelab/main.py
```

Na wijziging:

```bash
cd /opt/challengelab
source venv/bin/activate
python3 -m py_compile main.py
sudo systemctl restart challengelab
curl http://127.0.0.1:8000/catalog
```

## Backup pre-DB01

Belangrijk om te bewaren:

WEB01:

```text
/opt/challengelab/main.py
/var/www/challenges/index.html
/etc/nginx/sites-available/challenges
/etc/systemd/system/challengelab.service
/opt/challengelab/challengelab.db
```

DOCKER01:

```text
/home/team/challengelab/challenges/
```

De SQLite database kan apart als backup worden bewaard, maar hoort niet in Git.

SSH private keys horen eveneens niet in Git.
