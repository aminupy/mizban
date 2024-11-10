import os

import aiofiles

from app.core import settings


async def save_file(file):
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)

    async with aiofiles.open(file_path, "wb") as buffer:
        while content := await file.read(1024 * 1024):
            await buffer.write(content)

    return file_path


async def stream_file(file_path):
    async with aiofiles.open(file_path, mode="rb") as f:
        while chunk := await f.read(1024 * 1024):  # Adjust chunk size as needed
            yield chunk


async def get_all_files():
    files = os.listdir(settings.UPLOAD_DIR)
    return files
