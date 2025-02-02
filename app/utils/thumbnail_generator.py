from pathlib import Path

from PIL import Image

from app.core.config import settings


async def generate_thumbnail(file_path: str) -> Path | None:
    file_path = Path(file_path)
    thumb_path = settings.THUMBNAIL_DIR / f"{file_path.stem}.jpg"
    try:
        if file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif"]:
            img = Image.open(file_path)
            img.thumbnail((200, 200))
            img.save(thumb_path, "JPEG")
        else:
            return None
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None
    return thumb_path if thumb_path.exists() else None
