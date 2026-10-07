# API

De API draait op FastAPI achter Nginx.

Extern:

```text
http://192.168.10.22/api/
```

Intern:

```text
http://127.0.0.1:8000/
```

## Endpoints

### GET /

Healthcheck.

Voorbeeld:

```json
{
  "status": "ok",
  "message": "ChallengeLab API draait"
}
```

### GET /catalog

Geeft de challengecatalogus terug.

De portal gebruikt dit endpoint om het challenge-overzicht automatisch op te bouwen.

### POST /session/start

Maakt:

- nieuwe UUID voor de sessie;
- SQLite-record;
- challenge 1 container;
- Traefik-route.

Geeft onder andere terug:

```json
{
  "session_id": "...",
  "status": "active",
  "current": 1,
  "total": 10,
  "instance_id": "abcd1234",
  "url": "/c/abcd1234/?session=..."
}
```

### GET /session/{session_id}

Geeft de huidige voortgang en actieve challenge terug.

Wordt ook gebruikt om een sessie vanuit localStorage in de browser te herstellen.

### POST /session/{session_id}/answer

Body:

```json
{
  "answer": "..."
}
```

Bij fout antwoord blijft dezelfde challenge actief.

Bij correct antwoord:

1. huidige challengecontainer verwijderen;
2. current_index ophogen;
3. volgende container starten;
4. sessie bijwerken;
5. nieuwe URL retourneren.

Na challenge 10 wordt de sessie `completed`.

### DELETE /session/{session_id}

Verwijdert:

- actieve container;
- SQLite-sessierecord.

## Swagger

Door `root_path="/api"` werkt Swagger achter Nginx via:

```text
http://192.168.10.22/api/docs
```

OpenAPI:

```text
http://192.168.10.22/api/openapi.json
```
