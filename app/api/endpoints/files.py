import mimetypes

from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse, ORJSONResponse

from app.core import settings
from app.services import save_file, stream_file, get_all_files

router = APIRouter()


# File upload endpoint
@router.post(
    "/upload/", response_class=ORJSONResponse, status_code=status.HTTP_201_CREATED
)
async def upload_file(file: UploadFile = File(...)):
    await save_file(file)

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
        headers={
            "Content-Length": str(file_path.stat().st_size)
        }
    )


# List all files in the directory
@router.get("/files/", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def list_files():
    files = await get_all_files()
    return {"files": files}
