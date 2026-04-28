# CRM Agentic AI

Un CRM cu agenți AI care analizează lead-uri în timp real, calculează scorul de intenție și generează sugestii personalizate pentru vânzători.

Interfața are 3 coloane:
- **Activity Feed** — activitățile agenților AI în timp real
- **Intent Pipeline** — lead-urile sortate după scorul de intenție calculat de AI
- **Co-pilot Sidebar** — insights și draft mesaj personalizat per lead

---

## Pornire rapidă

### 1. Cerințe

**Windows / macOS**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalat și pornit

**Linux**
```bash
# Instalare Docker Engine + plugin Compose
curl -fsSL https://get.docker.com | sh
sudo apt-get install -y docker-compose-plugin   # Debian/Ubuntu
# sau
sudo dnf install -y docker-compose-plugin       # Fedora/RHEL

# Pornește daemon-ul
sudo systemctl start docker

# Opțional: rulează Docker fără sudo
sudo usermod -aG docker $USER && newgrp docker
```

### 2. Clonează repo-ul

```bash
git clone https://github.com/06cezar/-CRM-Agentic-AI.git
cd -CRM-Agentic-AI
```

### 3. Pornește serviciile

```bash
docker compose up -d
```

> Migrațiile bazei de date rulează automat la pornire.

### 4. Descarcă modelul AI (o singură dată, ~2GB)

```bash
docker exec crm-ollama ollama pull llama3.2:3b
```

> **llama3.2:3b** — model local de la Meta, rulează complet pe mașina ta (fără cloud, fără costuri). Folosit de `LeadResearchAgent` pentru a extrage semnale de cumpărare dintr-un profil de lead și a calcula un scor de intenție 0–100.

### 5. Accesează aplicația

| Serviciu | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Core API (docs) | http://localhost:8000/docs |
| AI Service (docs) | http://localhost:8001/docs |

---

## Ce poate face momentan

- **Autentificare** — login/logout cu JWT
- **Lead Pipeline** — adaugă, vizualizează și șterge lead-uri
- **Research Agent** — apasă "Research" pe un lead și AI-ul analizează profilul, extrage semnale de cumpărare și calculează un scor de intenție
- **Research automat** — la crearea unui lead, research-ul pornește automat în background
- **Activity Feed** — toate acțiunile agenților AI apar în timp real (polling 30s)
- **Dashboard stats** — header-ul afișează live: lead-uri hot, acțiuni AI azi, valoare pipeline

---

## Stack

- **Frontend:** Next.js 16 + React 19 + TypeScript + Tailwind
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **AI Service:** FastAPI + Ollama (llama3.2:3b)
- **Infra:** Docker Compose
