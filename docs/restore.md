# Restore-notities

## WEB01

Benodigd:
- nginx
- python3 + venv
- openssh-client
- FastAPI + Uvicorn

Plaats:
- `web01/app/main.py` -> `/opt/challengelab/main.py`
- `web01/systemd/challengelab.service` -> `/etc/systemd/system/challengelab.service`
- `web01/nginx/challenges` -> `/etc/nginx/sites-available/challenges`
- portal -> `/var/www/challenges/index.html`

Maak op WEB01 een SSH-key voor toegang tot DOCKER01:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/challengelab_docker
ssh-copy-id -i ~/.ssh/challengelab_docker.pub team@192.168.10.23
```

## DOCKER01

Installeer Docker, maak `challenge-net`, start Traefik en build de challenge-images vanuit `docker01/challenges/`.

## Geen DB01

Deze snapshot gebruikt SQLite op WEB01:
```text
/opt/challengelab/challengelab.db
```
