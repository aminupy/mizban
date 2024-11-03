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


@router.get("/download/{filename}")
async def download_file(filename: str):
    from pathlib import Path
    import aiofiles
    from fastapi.responses import StreamingResponse
    file_path = settings.UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    async def file_iterator(file_path: Path):
        async with aiofiles.open(file_path, mode='rb') as f:
            while chunk := await f.read(1024 * 1024):  # Adjust chunk size as needed
                yield chunk
    return StreamingResponse(file_iterator(file_path), media_type='application/octet-stream')

# List all files in the directory
@router.get("/files/", response_class=ORJSONResponse)
async def list_files():
    files = await get_all_files()
    return {
        "files": files
    }
