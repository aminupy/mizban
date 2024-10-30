from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, ORJSONResponse

from app.core import settings
from app.services import save_file, get_all_files


router = APIRouter()

# File upload endpoint
@router.post("/upload/", response_class=ORJSONResponse)
async def upload_file(file: UploadFile = File(...)):
    await save_file(file)

    return {
            "filename": file.filename,
            "message": "File uploaded successfully"
            }


# List all files in the directory
@router.get("/files/", response_class=ORJSONResponse)
async def list_files():
    files = await get_all_files()
    return {
        "files": files
    }
