# WEB01

**IP:** 192.168.10.22

WEB01 verzorgt de portal, API en reverse proxy.

## Software

- Ubuntu Server
- Nginx
- Python 3
- Python virtual environment
- FastAPI
- Uvicorn
- OpenSSH client
- SQLite via Python stdlib

## Belangrijke paden

```text
/opt/challengelab/main.py
/opt/challengelab/venv/
/opt/challengelab/challengelab.db
/var/www/challenges/index.html
/etc/nginx/sites-available/challenges
/etc/nginx/sites-enabled/challenges
/etc/systemd/system/challengelab.service
/home/team/.ssh/challengelab_docker
```

## Python omgeving

```bash
sudo mkdir -p /opt/challengelab
sudo chown team:team /opt/challengelab
cd /opt/challengelab

python3 -m venv venv
source venv/bin/activate
pip install fastapi "uvicorn[standard]"
```

## FastAPI

FastAPI draait alleen lokaal:

```text
127.0.0.1:8000
```

Dit is bewust: externe clients bereiken de API alleen via Nginx onder `/api/`.

De pre-DB01 bron staat in:

```text
web01/app/main.py
```

## Systemd

Servicebestand:

```text
/etc/systemd/system/challengelab.service
```

Activeren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now challengelab
sudo systemctl status challengelab
```

Logs:

```bash
sudo journalctl -u challengelab -n 100 --no-pager
sudo journalctl -u challengelab -f
```

## Nginx

Siteconfig:

```text
/etc/nginx/sites-available/challenges
```

Activeren:

```bash
sudo ln -s /etc/nginx/sites-available/challenges /etc/nginx/sites-enabled/challenges
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Routes:

| Pad | Bestemming |
|---|---|
| / | statische portal |
| /api/ | FastAPI 127.0.0.1:8000 |
| /c/ | Traefik op DOCKER01:8081 |

## SSH richting DOCKER01

WEB01 gebruikt een aparte sleutel:

```text
/home/team/.ssh/challengelab_docker
```

Voorbeeld aanmaken:

```bash
ssh-keygen -t ed25519 -f /home/team/.ssh/challengelab_docker
```

Publieke sleutel toevoegen aan `~team/.ssh/authorized_keys` op DOCKER01.

Test:

```bash
ssh -i /home/team/.ssh/challengelab_docker team@192.168.10.23 docker ps
```

De private key hoort nooit in Git.
