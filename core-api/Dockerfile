# Folosim o versiune slim, dar adăugăm manual ce lipsește
FROM python:3.11-slim

# Setăm variabile de mediu pentru Python (fără fișiere .pyc și log-uri instantanee)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instalăm dependențele de sistem
# - git: pentru a putea schimba branch-uri din container
# - build-essential & libpq-dev: necesare pentru driverele de Postgres
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalăm dependențele Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiem codul (în dev, volumul va suprascrie asta, dar e bine pentru build-ul final)
COPY . .

<<<<<<< HEAD
# Expunem portul FastAPI
EXPOSE 8000

# Pornim serverul cu --reload pentru Hot Reloading
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
=======
RUN chmod +x entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
>>>>>>> 73ccae4c00259b4ca761854f4cd41ebed3de95ea
