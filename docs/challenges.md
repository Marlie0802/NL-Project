# Challenges

ChallengeLab bevat in de pre-DB01 versie 10 challenges. Iedere challenge is een los Docker-image met Nginx en een statische HTML-pagina.

## Gemeenschappelijke opbouw

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

Elke challenge ontvangt de sessie-ID via:

```text
?session=<uuid>
```

Het antwoord wordt niet lokaal in JavaScript gevalideerd. De pagina stuurt het antwoord naar:

```text
POST /api/session/<session-id>/answer
```

Na een goed antwoord wacht `waitForChallenge(url)` tot de volgende container via Traefik bereikbaar is.

## Overzicht

### 1. De vergeten medewerker

- ID: `vergeten-medewerker`
- Image: `challengelab/vergeten-medewerker:1.0`
- Niveau: Beginner
- Categorie: Authenticatie
- Antwoord: `tvos`

Student combineert accountinformatie, HR-mutaties en loginlogs om een actief account van een oud-medewerker te vinden.

### 2. De gebroken toegangscode

- ID: `gebroken-toegangscode`
- Image: `challengelab/gebroken-toegangscode:1.0`
- Niveau: Gemiddeld
- Categorie: Authenticatie
- Antwoord: `47218396`

Student koppelt request-ID REC-8821 aan twee codefragmenten.

### 3. Bericht van Directeur

- ID: `bericht-van-directeur`
- Image: `challengelab/bericht-van-directeur:1.0`
- Niveau: Beginner
- Categorie: Phishing
- Antwoord: `secure-paymentdesk.net`

Student herkent phishing aan afwijkend domein, tijdsdruk, geheimhouding en een extern betaalportaal.

### 4. Wie kun je vertrouwen?

- ID: `wie-kun-je-vertrouwen`
- Image: `challengelab/wie-kun-je-vertrouwen:1.0`
- Niveau: Gemiddeld
- Categorie: Social engineering
- Antwoord: `persoon-b`

Student vergelijkt drie contactpogingen met interne verificatierichtlijnen.

### 5. De verkeerde deur

- ID: `de-verkeerde-deur`
- Image: `challengelab/de-verkeerde-deur:1.0`
- Niveau: Beginner
- Categorie: Netwerk / firewall
- Antwoord: `22`

Student bepaalt welke beheerservice ten onrechte vanaf internet bereikbaar is.

Belangrijk: in de uiteindelijke versie wordt poort 22 **niet rood gemarkeerd**, zodat het antwoord niet visueel wordt weggegeven.

### 6. De verboden route

- ID: `de-verboden-route`
- Image: `challengelab/de-verboden-route:1.0`
- Niveau: Gemiddeld
- Categorie: Netwerk / firewall
- Antwoord: `user-db`

Student vergelijkt netwerkbeleid met firewallregels en ontdekt dat USER-NET niet rechtstreeks DB-NET mag bereiken.

### 7. De ontbrekende minuten

- ID: `de-ontbrekende-minuten`
- Image: `challengelab/de-ontbrekende-minuten:1.0`
- Niveau: Gemiddeld
- Categorie: Forensics
- Antwoord: `mvandermeer`

Student combineert login-, bestands- en netwerklogs rond een gat in de logging.

### 8. Wie was het?

- ID: `wie-was-het`
- Image: `challengelab/wie-was-het:1.0`
- Niveau: Gevorderd
- Categorie: Forensics
- Antwoorden: `rkuiper`, `robin kuiper`

Student koppelt badgegegevens, login, DHCP/IP, fileserveractiviteit en USB-audit aan elkaar.

### 9. Het geheime bericht

- ID: `het-geheime-bericht`
- Image: `challengelab/het-geheime-bericht:1.0`
- Niveau: Beginner
- Categorie: Encryptie
- Antwoord: `blauw`

Student gebruikt Caesar shift 3 om de tekst "HET WACHTWOORD IS BLAUW" te ontcijferen.

### 10. De echte Kluis

- ID: `de-echte-kluis`
- Image: `challengelab/de-echte-kluis:1.0`
- Niveau: Gevorderd
- Categorie: Databeveiliging
- Antwoord: `salarissen.xlsx`

Student vergelijkt classificaties met toegangsrechten en ontdekt dat vertrouwelijke salarisdata te breed toegankelijk is.
