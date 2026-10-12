import os, time, uuid, shutil
from pathlib import Path
from fastapi import APIRouter, File, UploadFile

from app.core.exceptions import BusinessException
from app.core.response import Response
from app.config import MAX_FILE_SIZE, ALLOWED_EXTENSIONS, UPLOAD_DIR

router = APIRouter(prefix="/files", tags=["文件管理"])


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    if not file.filename:
        raise BusinessException(message="403文件名不能为空")

    orignal_name = os.path.basename(file.filename)
    ext = Path(orignal_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持文件后缀： {ext}")

    if file.size and file.size > MAX_FILE_SIZE:
        raise BusinessException(
            message=f"文件大小不能超过： {MAX_FILE_SIZE//1024//1024} MB"
        )

    disk_name = f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = UPLOAD_DIR / disk_name

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return Response.success(
        data={
            "orignal_name": orignal_name,
            "disk_name": disk_name,
            "size": file.size,
            "url": f"/uploads/{disk_name}",
        }
    )
