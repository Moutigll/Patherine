# Patherine

This project creates a SQLite database to store and analyze Discord messages, users, channels, and reactions. It enforces constraints like:
- One message per user/channel/day.
- One reaction per user/message.

## 🛠 Setup (Python 3.8+ recommended)

### 1. Clone the repo

```bash
git clone <repo-url>
cd <repo-folder>
```

### 2. Create a virtual environment (optional but recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the script

```bash
python main.py
```

This will create a file `discord_analysis.db` in the current directory.

## 📁 Files

- `main.py` → Script to create the database schema
- `requirements.txt` → Python dependencies
