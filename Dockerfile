# Multi-stage build per ottimizzare l'immagine finale
FROM python:3.11-slim

# Imposta variabili di ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Crea la directory di lavoro
WORKDIR /app

# Installa le dipendenze di sistema (se necessarie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia i requirements e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia il codice dell'applicazione
COPY . .

# Crea le cartelle necessarie
RUN mkdir -p /app/users_data /app/data

# Espone la porta
EXPOSE 3020

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:3020/', timeout=5)" || exit 1

# Avvia l'applicazione
CMD ["python", "app.py"]
