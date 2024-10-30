import aiofiles
import os
import shutil

from app.core.config import settings


async def save_file(file):
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)

    async with aiofiles.open(file_path, "wb") as buffer:
        while content := await file.read(1024 * 1024):
            await buffer.write(content)

    return file_path


async def get_all_files():
    files = os.listdir(settings.UPLOAD_DIR)
    return files