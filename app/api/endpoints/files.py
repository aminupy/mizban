import aiofiles
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse, ORJSONResponse
from starlette.responses import StreamingResponse

from app.core import settings
from app.services import save_file, get_all_files


router = APIRouter()

# File upload endpoint
@router.post("/upload/", response_class=ORJSONResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    await save_file(file)

    return {
            "filename": file.filename,
            "message": "File uploaded successfully"
            }


@router.get("/download/{filename}", response_class=StreamingResponse, status_code=status.HTTP_200_OK)
async def download_file(filename: str):
    file_path = settings.UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    async def file_iterator():
        async with aiofiles.open(file_path, mode='rb') as f:
            while chunk := await f.read(1024 * 1024):  # Adjust chunk size as needed
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(file_path.stat().st_size)
        }

    )
# List all files in the directory
@router.get("/files/", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def list_files():
    files = await get_all_files()
    return {
        "files": files
    }
