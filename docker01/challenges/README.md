# Challenge images

De pre-DB01 omgeving gebruikt 10 losse Docker-images. Iedere challenge-map hoort deze structuur te hebben:

```text
<challenge-id>/
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

Images:

1. `challengelab/vergeten-medewerker:1.0`
2. `challengelab/gebroken-toegangscode:1.0`
3. `challengelab/bericht-van-directeur:1.0`
4. `challengelab/wie-kun-je-vertrouwen:1.0`
5. `challengelab/de-verkeerde-deur:1.0`
6. `challengelab/de-verboden-route:1.0`
7. `challengelab/de-ontbrekende-minuten:1.0`
8. `challengelab/wie-was-het:1.0`
9. `challengelab/het-geheime-bericht:1.0`
10. `challengelab/de-echte-kluis:1.0`

De FastAPI-backend start per sessie steeds één instance en geeft die Traefik-labels voor een route onder `/c/<instance-id>/`.

> De HTML-bronbestanden zijn inhoudelijk onderdeel van de challenges. Kopieer de actuele `html/index.html` uit de challenge-mappen op DOCKER01 wanneer je een exacte server-snapshot wilt bewaren.
