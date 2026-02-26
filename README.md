# MusicAgent

## Backend Setup (FastAPI + MongoDB)

### 1. Go to the backend folder

```powershell
cd backend
```

### 2. Create a virtual environment (if needed)

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment (Windows PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

If `pip` is missing in the virtual environment, run:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5. Configure environment variables

Create/update `backend/.env` with your MongoDB connection string:

```env
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<db_name>?retryWrites=true&w=majority
MONGODB_DB_NAME=deepbeats
```

Note: the current code also supports `MONGO_URL`, but `MONGODB_URI` is the preferred key.

### 6. Run the FastAPI server

From the `backend/` folder:

```powershell
uvicorn app.main:app --reload
```

### 7. Test database endpoints

Open these in your browser or Postman:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/users/db-ping`
- `POST http://127.0.0.1:8000/users/`
- `GET http://127.0.0.1:8000/users/`
}
```
