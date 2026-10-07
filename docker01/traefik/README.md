# Traefik op DOCKER01

ChallengeLab gebruikt Docker-netwerk `challenge-net`.

## Netwerk

```bash
docker network inspect challenge-net >/dev/null 2>&1 || docker network create challenge-net
```

## Traefik

```bash
docker run -d \
  --name challengelab-proxy \
  --restart unless-stopped \
  --network challenge-net \
  -p 8081:80 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  traefik:v3 \
  --entrypoints.web.address=:80 \
  --providers.docker=true \
  --providers.docker.exposedbydefault=false \
  --providers.docker.network=challenge-net
```

WEB01 proxyt `/c/` naar `http://192.168.10.23:8081`.
