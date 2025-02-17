import mimetypes

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import ORJSONResponse, StreamingResponse

from app.core import settings
from app.services import get_all_files, save_file, stream_file
from app.utils import generate_thumbnail

router = APIRouter()


# File upload endpoint
@router.post(
    "/upload/", response_class=ORJSONResponse, status_code=status.HTTP_201_CREATED
)
async def upload_file(file: UploadFile = File(...)):
    saved_file = await save_file(file)
    await generate_thumbnail(saved_file)
    return {"filename": file.filename, "message": "File uploaded successfully"}


@router.get(
    "/download/{filename}",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
)
async def download_file(filename: str):
    file_path = settings.UPLOAD_DIR / filename
    mimetype = mimetypes.guess_type(file_path)[0]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(
        stream_file(file_path),
        media_type=mimetype or "application/octet-stream",
        headers={"Content-Length": str(file_path.stat().st_size)},
    )


@router.get("/thumbnails/{filename}", response_class=StreamingResponse)
async def get_thumbnail(filename: str):
    thumb_path = settings.THUMBNAIL_DIR / f"{filename}.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return StreamingResponse(stream_file(thumb_path), media_type="image/jpeg")


# List all files in the directory
@router.get("/files/", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def list_files():
    files = await get_all_files()
    return {"files": files}
