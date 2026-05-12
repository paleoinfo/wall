# Docker Setup per WALL - Image Mosaic Gallery

## 📋 Panoramica

Questa applicazione è stata containerizzata con Docker per facilitare il deployment e lo sviluppo in ambienti isolati e consistenti.

## 📁 File Docker Creati

- **`Dockerfile`**: Definisce l'immagine Docker dell'applicazione
- **`docker-compose.yml`**: Orestra la containerizzazione e la gestione dei volumi
- **`.dockerignore`**: Esclude file non necessari dall'immagine Docker

## 🚀 Quick Start

### Avviare l'applicazione

```bash
docker-compose up -d
```

Accedi a http://localhost:3020

### Visualizzare i log

```bash
docker-compose logs -f wall
```

### Arrestare l'applicazione

```bash
docker-compose down
```

## 🔧 Configurazione

Tutte le variabili di configurazione sono definite nel file `.env`:

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `SSO_MODE` | Modalità SSO ('dev' o 'production') | `dev` |
| `JWT_SECRET` | Secret per validare i token JWT | (vuoto) |
| `PORTAL_URL` | URL del portale SSO | `http://localhost:5000` |
| `SERVER_SECRET_KEY` | Chiave segreta per le sessioni Flask | `dev-secret-change-in-production` |
| `DEBUG` | Abilita debug mode | `False` |
| `DEV_USER_EMAIL` | Email utente di test (solo in dev) | `demo@example.com` |
| `FLASK_HOST` | Host di bind (0.0.0.0 per Docker) | `0.0.0.0` |
| `FLASK_PORT` | Porta di ascolto | `3020` |

### Esempio configurazione di produzione

Crea un file `.env` con:

```env
SSO_MODE=production
JWT_SECRET=<tuo-secret-jwt-complesso>
PORTAL_URL=https://sso.tuodominio.it
SERVER_SECRET_KEY=<tua-chiave-segreta-complessa>
DEBUG=False
```

Quindi avvia: `docker-compose up -d`

## 📦 Volumi Persistenti

L'applicazione utilizza due volumi Docker per persistere i dati:

- **`wall_users_data`**: Immagini caricate dagli utenti (`/app/users_data`)
- **`wall_data`**: File di configurazione e whitelist (`/app/data`)

Per ispezionare i volumi:
```bash
docker volume ls
docker volume inspect wall_users_data
```

Per cancellare i volumi (attenzione: cancella tutti i dati!):
```bash
docker volume rm wall_users_data wall_data
```

## 🔍 Troubleshooting

### L'app non è raggiungibile su localhost:3020

1. Verifica che il container sia in esecuzione:
   ```bash
   docker-compose ps
   ```

2. Controlla i log per errori:
   ```bash
   docker-compose logs wall
   ```

3. Verifica che la porta non sia in uso:
   ```bash
   lsof -i :3020  # macOS/Linux
   netstat -ano | findstr :3020  # Windows
   ```

### Errore di connessione al portale SSO

Assicurati che `PORTAL_URL` sia corretto e raggiungibile dal container. Se usi `localhost`, usa `host.docker.internal` invece (su Docker Desktop):

```env
PORTAL_URL=http://host.docker.internal:5000
```

### I dati degli utenti vengono persi

Verifica che i volumi Docker siano correttamente montati:

```bash
docker volume ls | grep wall
```

Se i volumi non esistono, ricreali:
```bash
docker-compose down -v
docker-compose up -d
```

## 🔐 Sicurezza in Produzione

1. **Cambiar `SERVER_SECRET_KEY`**: Genera una chiave casuale sicura
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Configura `JWT_SECRET`**: Usa il secret del tuo portale SSO

3. **Imposta `DEBUG=False`**: Mai abilitare in produzione

4. **Usa `https://`** per tutte le URL (con reverse proxy/nginx)

5. **Aggiorna le immagini**: Mantieni Python e le dipendenze aggiornate
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

## 📈 Scalabilità

Per multi-instance dietro load balancer (es. Nginx):

```yaml
services:
  wall-1:
    # ... come prima
  
  wall-2:
    # ... stessa config, diverse porte interne
    
  nginx:
    image: nginx:alpine
    # ... configurazione load balancing
```

## 🐛 Debug

Per accedere al container in interattivo:

```bash
docker-compose exec wall /bin/bash
```

All'interno del container:
```bash
# Visualizzare le immagini di un utente
ls users_data/demo/

# Controllare i log dell'app
cat /app/data/whitelist.json

# Testare la connessione SSO
python -c "import requests; requests.get('PORTAL_URL')"
```

## 📚 Riferimenti

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Flask in Docker](https://flask.palletsprojects.com/en/latest/deploying/docker/)
