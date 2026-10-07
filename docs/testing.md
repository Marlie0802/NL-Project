# Testen en troubleshooting

## WEB01 controleren

### FastAPI service

```bash
sudo systemctl status challengelab --no-pager
```

### API lokaal

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/catalog
```

### API via Nginx

```bash
curl http://192.168.10.22/api/catalog
```

### Syntaxcontrole

Voor wijzigingen aan `main.py`:

```bash
cd /opt/challengelab
source venv/bin/activate
python3 -m py_compile main.py
```

Geen output betekent dat de Python-syntax geldig is.

### Logs

```bash
sudo journalctl -u challengelab -n 50 --no-pager
```

## DOCKER01 controleren

```bash
docker ps
docker ps -a --filter "name=challenge-"
docker network inspect challenge-net
```

Traefik:

```bash
curl -I http://192.168.10.23:8081
```

Een 404 op `/` is normaal.

## Volledige route testen

Start een sessie via de portal en bekijk de actieve URL, bijvoorbeeld:

```text
http://192.168.10.22/c/dd33a63b/?session=...
```

Of test Traefik rechtstreeks:

```bash
curl -I http://192.168.10.23:8081/c/<instance-id>/
```

En via WEB01:

```bash
curl -I http://192.168.10.22/c/<instance-id>/
```

## Bekende problemen die tijdens de bouw zijn opgelost

### FastAPI 500: ssh niet gevonden

Fout:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'ssh'
```

Oorzaak: systemd PATH bevatte alleen de Python venv.

Fix:

```ini
Environment="PATH=/opt/challengelab/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

De uiteindelijke backend gebruikt bovendien expliciet:

```text
/usr/bin/ssh
```

### Swagger Failed to load API definition

Oorzaak: FastAPI draaide achter `/api/`.

Fix:

```python
app = FastAPI(
    title="ChallengeLab API",
    root_path="/api"
)
```

### 404 direct na volgende challenge

Oorzaak: Traefik had de nieuwe Docker-router nog niet ontdekt.

Fix: `waitForChallenge(url)` pollt de URL voordat de browser redirect.

### Method Not Allowed bij Start challenge

Oorzaak: frontend gebruikte oude losse challenge-endpoint terwijl backend naar sessies/catalogus was aangepast.

Fix: portal is daarna volledig omgebouwd naar één `POST /api/session/start` flow.

### Nginx 502 Bad Gateway

Controleer:

```bash
sudo systemctl status challengelab
curl http://127.0.0.1:8000/
```

Een 502 betekent meestal dat Uvicorn/FastAPI niet luistert op poort 8000.

### Python syntaxfout bij toevoegen challenge

Altijd eerst:

```bash
python3 -m py_compile main.py
```

Daarna pas:

```bash
sudo systemctl restart challengelab
```
