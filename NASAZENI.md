# 🚀 Návod na nasazení Lugog Clicker na web

## Možnost 1: Railway (DOPORUČENO - nejjednodušší)

1. **Zaregistruj se na [Railway.app](https://railway.app)** (můžeš použít GitHub účet)

2. **Vytvoř nový projekt**:
   - Klikni na "New Project"
   - Vyber "Deploy from GitHub repo"
   - Vyber tento repozitář

3. **Nastav proměnné prostředí**:
   - V projektu klikni na "Variables"
   - Přidej: `SECRET_KEY` = nějaký náhodný dlouhý string (např. `openssl rand -hex 32`)

4. **Nasazení proběhne automaticky!**
   - Railway automaticky detekuje Python projekt
   - Použije `Procfile` pro spuštění
   - Aplikace bude dostupná na URL typu `https://tvoje-app.railway.app`

## Možnost 2: Render

1. **Zaregistruj se na [Render.com](https://render.com)** (můžeš použít GitHub účet)

2. **Vytvoř nový Web Service**:
   - Klikni na "New +" → "Web Service"
   - Připoj svůj GitHub repozitář
   - Vyber tento repozitář

3. **Nastavení**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - Render automaticky použije `render.yaml` pokud existuje

4. **Environment Variables**:
   - V sekci "Environment" přidej:
     - `SECRET_KEY` = nějaký náhodný dlouhý string

5. **Deploy!**
   - Aplikace bude dostupná na URL typu `https://tvoje-app.onrender.com`

## Možnost 3: PythonAnywhere (Free tier)

1. **Zaregistruj se na [PythonAnywhere.com](https://www.pythonanywhere.com)**

2. **Nahraj soubory**:
   - V Files tab nahraj všechny soubory projektu
   - Nebo použij Git: `git clone https://github.com/tvuj-username/LugogClicker.git`

3. **Nastav Web App**:
   - Jdi do "Web" tab
   - Klikni "Add a new web app"
   - Vyber Flask a Python 3.10
   - Nastav source code na `/home/tvuj-username/LugogClicker`

4. **Uprav WSGI file**:
   - V "Web" tab klikni na WSGI configuration file
   - Uprav na:
   ```python
   import sys
   path = '/home/tvuj-username/LugogClicker'
   if path not in sys.path:
       sys.path.append(path)
   
   from app import app as application
   ```

5. **Nastav proměnné prostředí**:
   - V "Web" tab → "Environment variables"
   - Přidej: `SECRET_KEY` = nějaký náhodný dlouhý string

6. **Reload web app**

## ⚠️ Důležité poznámky

- **SQLite databáze**: Databáze bude na serveru, ale při restartu se může resetovat (záleží na platformě)
- **Session soubory**: Flask-Session používá filesystem, což může být problém na některých platformách
- **Statické soubory**: Obrázky v `obrazky/` budou dostupné, ale ujisti se, že jsou v repozitáři
- **Free tier limity**: 
  - Railway: $5 free kredit měsíčně
  - Render: Free tier má sleep mode (aplikace se uspí po 15 min nečinnosti)
  - PythonAnywhere: Free tier má limity na CPU a bandwidth

## 🔧 Pokud máš problémy

1. **Zkontroluj logy** na platformě (Railway/Render mají sekci Logs)
2. **Ověř, že všechny soubory jsou v repozitáři** (včetně `obrazky/`)
3. **Zkontroluj, že `SECRET_KEY` je nastavená**
4. **Ujisti se, že port je správně nastaven** (gunicorn to řeší automaticky)

## 📝 Po nasazení

Aplikace bude dostupná na URL, kterou ti platforma poskytne. Můžeš ji sdílet s ostatními!

---

**Hodně štěstí s nasazením! 🎮**

