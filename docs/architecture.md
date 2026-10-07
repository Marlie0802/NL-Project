# Architectuur

Deze documentatie beschrijft de werkende ChallengeLab-opzet **vóór de migratie naar DB01/PostgreSQL**.

## Hosts

| Host | IP | Functie |
|---|---|---|
| WEB01 | 192.168.10.22 | Nginx, statische portal, FastAPI/Uvicorn, SQLite-sessies |
| DOCKER01 | 192.168.10.23 | Docker, Traefik, challenge-containers |

## Verkeersstroom

```text
Browser
  |
  | HTTP :80
  v
WEB01 / Nginx
  |-- /          -> /var/www/challenges/index.html
  |-- /api/      -> 127.0.0.1:8000 (FastAPI)
  '-- /c/        -> 192.168.10.23:8081 (Traefik)
                                |
                                v
                        challenge-net
                                |
                                v
                        challenge container :80
```

## Waarom Traefik

Elke challenge krijgt een willekeurig instance-ID, bijvoorbeeld:

```text
6c7de507
```

De URL wordt:

```text
http://192.168.10.22/c/6c7de507/
```

FastAPI start de container met Traefik-labels. Traefik leest deze labels via de Docker socket en maakt automatisch de juiste route. Daardoor zijn geen losse hostpoorten per challenge nodig.

## Sessies

De pre-DB01 versie gebruikt SQLite:

```text
/opt/challengelab/challengelab.db
```

Tabel:

```text
sessions
|- id
|- current_index
|- current_instance
|- status
'- created_at
```

Een sessie start challenge 1. Na een correct antwoord:

1. huidige container wordt verwijderd;
2. current_index wordt verhoogd;
3. volgende challengecontainer wordt gestart;
4. SQLite wordt bijgewerkt;
5. browser wordt automatisch naar de nieuwe URL gestuurd.

## Challenge readiness

Traefik heeft soms enkele honderden milliseconden nodig om een nieuwe Docker-route te zien. Daarom bevatten de challengepagina's de functie `waitForChallenge(url)`.

Die probeert de nieuwe URL maximaal 20 keer met intervallen van 500 ms en redirect pas zodra de route HTTP 200 geeft. Dit voorkomt de eerdere korte 404 bij het wisselen tussen challenges.
