# 🖼️ Image Mosaic Gallery

Benvenuto in **Image Mosaic Gallery**, un'applicazione web moderna per la gestione e la visualizzazione creativa delle tue immagini personali.

Questa applicazione non è solo una semplice galleria, ma integra un sistema di posizionamento dinamico chiamato **WALL**, che trasforma le tue foto in un'opera di street-art digitale su un muro virtuale.

## ✨ Caratteristiche

- **🔐 Autenticazione Avanzata**: Integrazione con sistema SSO (Single Sign-On).
- **📂 Gestione Immagini**: Upload e cancellazione delle proprie foto in cartelle utente sicure.
- **🧱 Modalità WALL (Novità!)**:
  - Visualizza tutte le immagini su un muro virtuale di grandi dimensioni.
  - Algoritmo intelligente che evita l'occlusione totale delle immagini.
  - Rotazioni e dimensioni casuali per un effetto "street-art" premium.
  - Pulsante "Rigenera" per cambiare il layout istantaneamente.
- **🎨 Design Premium**: Interfaccia fluida, dark mode nel muro virtuale, ombre dinamiche e micro-animazioni.
- **📱 Responsive**: Funziona su desktop e dispositivi mobili.

## 🚀 Come Iniziare

### Opzione 1: Con Docker Compose (Consigliato) 🐳

#### Prerequisiti
- [Docker](https://www.docker.com/products/docker-desktop)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### Avvio

1. Clona la repository o scarica i file.
2. Copia il file di configurazione:
   ```bash
   cp .env.example .env
   ```
3. Configura le variabili in `.env` secondo le tue esigenze (vedi sezione [Configurazione](#configurazione)).
4. Avvia l'applicazione con Docker Compose:
   ```bash
   docker-compose up -d
   ```

L'applicazione sarà disponibile su `http://localhost:3020`.

**Comandi Docker Compose utili:**
```bash
# Visualizzare i log
docker-compose logs -f wall

# Arrestare il servizio
docker-compose down

# Ricostruire l'immagine (dopo modifiche al codice)
docker-compose build

# Riavviare il servizio
docker-compose restart wall
```

### Opzione 2: Installazione Locale

#### Prerequisiti

- Python 3.8+
- [Flask](https://flask.palletsprojects.com/)
- [PyJWT](https://pyjwt.readthedocs.io/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)

#### Procedura

1. Clona la repository o scarica i file.
2. Crea un ambiente virtuale:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Su Windows: venv\Scripts\activate
   ```
3. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
4. Configura le variabili d'ambiente (vedi sezione successiva).
5. Avvia il server:
   ```bash
   python app.py
   ```

L'applicazione sarà disponibile su `http://localhost:3020`.

### Configurazione

Crea un file `.env` nella root del progetto (puoi copiare `.env.example`) e configura le seguenti variabili:

```env
# Modalità SSO: 'dev' per sviluppo, 'production' per produzione
SSO_MODE=dev

# In produzione, configura il token JWT secret
JWT_SECRET=

# URL del portale SSO (in produzione)
PORTAL_URL=http://sso-portal:5000

# Chiave segreta per le sessioni Flask
SERVER_SECRET_KEY=dev-secret-change-in-production

# Email dell'utente di test in modalità 'dev'
DEV_USER_EMAIL=demo@example.com

# Modalità debug (mai in production!)
DEBUG=False
```

## 🛠️ Architettura del Progetto

- `app.py`: Backend Flask con gestione sessioni, SSO e filesystem.
- `templates/`:
  - `gallery.html`: Interfaccia principale della galleria e logica JavaScript del muro.
- `shared_modules/`:
  - `sso_middleware.py`: Logica di validazione token per l'integrazione SSO.
- `users_data/`: Cartella radice per le immagini degli utenti (organizzata per username).

## 🎨 Il Muro Virtuale (Wall Logic)

La logica del muro utilizza un algoritmo geometrico sviluppato in JavaScript che:
1. Carica metadati delle immagini (aspect ratio).
2. Genera posizioni e rotazioni casuali.
3. Calcola i vertici dei rettangoli ruotati.
4. Verifica che nessuna immagine copra interamente un'altra o sia interamente coperta, assicurando visibilità parziale per tutte le foto, tipico dei mosaici urban-art.


