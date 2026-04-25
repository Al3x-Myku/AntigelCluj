# BreezeTech Startup Application Mockup

This is a functional mockup of the BreezeTech startup portal (Smart Air Conditioning). It has been built using a Python backend (FastAPI) and a vanilla HTML/JS frontend, powered by a **MySQL/MariaDB** database. It includes a complete set of seeded dummy data (users, devices, service tickets, API keys) for testing purposes.

## Prerequisites

1. **Python 3.8+**
2. **MySQL** or **MariaDB**

### Installing MySQL / MariaDB

You can run MySQL locally in several ways.

**Option 1: Docker (Recommended)**
If you have Docker installed, you can quickly spin up a MariaDB instance:
```bash
docker run -d -p 3306:3306 -e MYSQL_ALLOW_EMPTY_PASSWORD=yes --name mariadb mariadb:latest
```
*(Note: `MYSQL_ALLOW_EMPTY_PASSWORD=yes` allows root access without a password, matching the default `.env` configuration. For production, always use secure passwords!)*

**Option 2: Local Installation (XAMPP / WAMP)**
- **Windows / macOS**: Download and install [XAMPP](https://www.apachefriends.org/index.html). Open the XAMPP Control Panel and start the "MySQL" module.

**Option 3: Direct Installation**
- **Windows**: Download the [MySQL Installer](https://dev.mysql.com/downloads/installer/).
- **macOS**: `brew install mysql`. Start it with `brew services start mysql`.
- **Linux (Ubuntu)**: `sudo apt install mysql-server`.

By default, the application will attempt to connect to MySQL at `mysql+pymysql://root:@localhost:3306/breezetech` (user `root`, no password, port `3306`). The app will try to automatically create the `breezetech` database if it doesn't exist.

## Installation & Setup

1. **Navigate to the app directory:**
   ```bash
   cd mockups/startup
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Environment variables are stored in the `.env` file. The defaults are set up for a local run:
```env
# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=9001

# Database (MySQL/MariaDB)
DATABASE_URL=mysql+pymysql://root:@localhost:3306/breezetech

# JWT
JWT_SECRET=breezetech-startup-demo-secret-2026
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
```

## Running the App

Start the FastAPI application using the provided `main.py` entrypoint (which runs `uvicorn`):

```bash
python -m backend.main
```

When the app starts for the first time, it will automatically connect to MySQL, create all the necessary tables, and seed the database with demo users, smart AC devices, service tickets, and API keys.

**Access the application:**
- Open your browser and go to: `http://localhost:9001`
- API documentation (Swagger) is available at: `http://localhost:9001/docs`

### Demo Credentials

You can log in with any of the seeded users. Here are a few examples:

- `admin@breezetech.ro` / `Admin!2026#`
- `marian.popescu@gmail.com` / `Marian2026!`
- `ioana.dumitrescu@yahoo.com` / `Ioana#Secure7`
