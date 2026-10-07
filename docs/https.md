# HTTPS

HTTPS was vóór DB01 nog niet daadwerkelijk ingericht, maar de architectuur is hier al geschikt voor.

## Gewenste situatie

```text
Browser
  |
  | HTTPS
  v
WEB01 / Nginx
  |
  | intern HTTP
  v
DOCKER01 / Traefik
  |
  | intern HTTP
  v
Challenge container
```

Alle publieke routes blijven op één hostnaam:

```text
https://<challenge-host>/
https://<challenge-host>/api/
https://<challenge-host>/c/<instance-id>/
```

De challenge-URL's zijn relatief (`/c/...`), waardoor zij automatisch HTTPS gebruiken zodra de portal via HTTPS bereikbaar is.

Er zijn dus geen TLS-certificaten nodig in iedere challengecontainer.

## Later toevoegen

Op WEB01:

1. DNS-naam naar WEB01 laten wijzen.
2. Nginx server_name instellen.
3. TLS-certificaat configureren, bijvoorbeeld met Let's Encrypt/certbot of een intern certificaat.
4. HTTP naar HTTPS redirecten.
5. `X-Forwarded-Proto` behouden.

Interne verbinding WEB01 -> DOCKER01 kan op het afgeschermde netwerk HTTP blijven gebruiken.
