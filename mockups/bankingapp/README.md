# SecurBank Banking Application Mockup

This is a functional mockup of the SecurBank online banking portal. It has been built using a Python backend (FastAPI) and a vanilla HTML/JS frontend, powered by a **MongoDB** database. It includes a complete set of seeded dummy data (users, accounts, cards, API keys) for testing purposes.

## Prerequisites

1. **Python 3.8+**
2. **MongoDB**

### Installing MongoDB

You can run MongoDB locally in several ways.

**Option 1: Docker (Recommended)**
If you have Docker installed, you can quickly spin up a MongoDB instance:
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

**Option 2: Local Installation**
- **Windows**: Download the [MongoDB Community Server MSI installer](https://www.mongodb.com/try/download/community) and follow the wizard.
- **macOS**: `brew tap mongodb/brew` and `brew install mongodb-community@7.0`. Start it with `brew services start mongodb-community@7.0`.
- **Linux (Ubuntu)**: Follow the [official installation guide](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/).

By default, the application will attempt to connect to MongoDB at `mongodb://localhost:27017`.

## Installation & Setup

1. **Navigate to the app directory:**
   ```bash
   cd mockups/bankingapp
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
SERVER_PORT=9000

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE=bankingapp

# JWT
JWT_SECRET=phishguard-banking-demo-secret-2026
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
```

## Running the App

Start the FastAPI application using the provided `main.py` entrypoint (which runs `uvicorn`):

```bash
python -m backend.main
```

When the app starts for the first time, it will automatically connect to MongoDB, create the necessary indexes, and seed the database with 20 demo users (and their accounts/cards).

**Access the application:**
- Open your browser and go to: `http://localhost:9000`
- API documentation (Swagger) is available at: `http://localhost:9000/docs`

### Demo Credentials

You can log in with any of the seeded users. Here are a few examples:

- `admin@securbank.ro` / `Admin!2026#`
- `andrei.popescu@gmail.com` / `Andrei2026!`
- `maria.ionescu@yahoo.com` / `Maria#Secure7`
