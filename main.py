import sys
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import files_router
from app.core import settings
from app.utils import lifespan, initialize_shared_folder


initialize_shared_folder(settings.UPLOAD_DIR)
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
    async_loop = "uvloop" if sys.platform == "linux" else "asyncio"
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000,
        loop=async_loop,
        http="httptools",
        log_level="critical"
    )

