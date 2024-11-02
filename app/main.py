from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import orjson

from app.api.endpoints import files
from app.core import settings
from app.utils.folder_util import initialize_shared_folder

initialize_shared_folder(settings.UPLOAD_DIR)
app = FastAPI()

# Include routers for different parts of the API
app.include_router(files.router, prefix="/api/files", tags=["Files"])

# Mount the shared files directory as a static path
app.mount("/storage", StaticFiles(directory=settings.UPLOAD_DIR), name="MizbanShared")



if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000, loop='uvloop', http='httptools')