import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import files_router
from app.core import settings
from app.utils import initialize_shared_folders, lifespan

initialize_shared_folders([settings.UPLOAD_DIR, settings.THUMBNAIL_DIR])

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers for different parts of the API
app.include_router(files_router, prefix="/api/files", tags=["Files"])

# Mount frontend
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        app=app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        loop=settings.ASYNC_LOOP,
        http=settings.HTTP_METHOD,
        log_level=settings.LOG_LEVEL,
    )
