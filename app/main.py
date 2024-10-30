from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import files
from app.core import settings

app = FastAPI()

# Include routers for different parts of the API
app.include_router(files.router, prefix="/api/files", tags=["Files"])

# Mount the shared files directory as a static path
app.mount("/storage", StaticFiles(directory=settings.UPLOAD_DIR), name="MizbanShared")
