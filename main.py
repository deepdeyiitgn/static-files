import os
import json
import shutil
import uuid
import mimetypes
import logging
import requests
import base64
import re
import glob
import yt_dlp
import asyncio
import aiofiles
import aiohttp
import urllib.parse
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Header, Cookie, UploadFile, File, Form, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError

# ==========================================
# 1. LOGGING & CONFIGURATION SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("QlynkHost")

HF_TOKEN = os.environ.get("HF_TOKEN")
SPACE_PASSWORD = os.environ.get("SPACE_PASSWORD")

api = HfApi(token=HF_TOKEN)
DATASET_REPO = os.environ.get("DATASET_REPO")

# ==========================================
# 2. ADVANCED FAST BOOT (LIFESPAN MANAGER)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global DATASET_REPO
    logger.info("Starting Qlynk Host Initialization Sequence...")
    
    try:
        if not DATASET_REPO:
            user_info = api.whoami()
            username = user_info.get("name")
            DATASET_REPO = f"{username}/my-private-storage"
            logger.info(f"Auto-detected Target Repo: {DATASET_REPO}")
        
        api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", private=True, exist_ok=True)
        logger.info("Dataset Repository Verified & Ready.")
        
        try:
            hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
            logger.info("Existing database (history.json) found.")
        except EntryNotFoundError:
            logger.warning("No database found. Initializing fresh history.json...")
            empty_db = {"total_files": 0, "total_size_bytes": 0, "files": []}
            with open("history.json", "w") as f:
                json.dump(empty_db, f, indent=4)
            api.upload_file(
                path_or_fileobj="history.json", 
                path_in_repo="history.json", 
                repo_id=DATASET_REPO, 
                repo_type="dataset"
            )
            logger.info("Fresh database initialized successfully.")
            
    except Exception as e:
        logger.error(f"CRITICAL STARTUP ERROR: Please check your HF_TOKEN permissions. Details: {e}")
    yield
    logger.info("Shutting down Qlynk Host...")

app = FastAPI(
    title="Qlynk Host Ultimate",
    description="Enterprise-grade private file hosting architecture using HF Datasets.",
    version="2.0.0",
    lifespan=lifespan
)

# ==========================================
# 3. DYNAMIC CORS (DOMAIN WHITELISTING)
# ==========================================
allowed_origins = [val for key, val in os.environ.items() if key.startswith("DOMAIN_")]
if not allowed_origins:
    allowed_origins = ["*"] 
    logger.info("CORS policy set to open (*). No specific domains whitelisted.")
else:
    logger.info(f"CORS Whitelisted Domains: {', '.join(allowed_origins)}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 4. UTILITY & DATABASE FUNCTIONS
# ==========================================
def format_size(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def get_db() -> Dict[str, Any]:
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Database Read Error: {e}")
        return {"total_files": 0, "total_size_bytes": 0, "files": []}

def save_db(db_data: Dict[str, Any]):
    db_data["total_files"] = len(db_data.get("files", []))
    db_data["total_size_bytes"] = sum(item.get("size_bytes", 0) for item in db_data.get("files", []))
    
    with open("history.json", "w") as f:
        json.dump(db_data, f, indent=4)
        
    api.upload_file(
        path_or_fileobj="history.json", 
        path_in_repo="history.json", 
        repo_id=DATASET_REPO, 
        repo_type="dataset"
    )

def verify_auth(password: str = Header(None), auth_token: str = Cookie(None)):
    token = password or auth_token
    if not token or token != SPACE_PASSWORD:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED: Access denied. Invalid Master Password.")
    return token

# ==========================================
# 5. CORE REST APIs (THE MEGA SYSTEM)
# ==========================================
@app.get("/api/rest", response_class=JSONResponse)
async def serve_mega_api_docs():
    """
    Direct API hit karne par (GET request) yeh JSON documentation reply mein aayega.
    """
    return {
        "status": "info",
        "version": "v2.0.0",
        "name": "Qlynk Host Enterprise API",
        "maker": "Deep Dey",
        "description": "Enterprise-grade private file hosting architecture API. Upload files directly or via URL, process media using yt-dlp, and manage metadata. JSON responses available by default.",
        "endpoints": [
            {"method": "GET", "path": "/api/rest", "description": "Fetch this API documentation (JSON response)"},
            {"method": "POST", "path": "/api/rest", "description": "Upload a new file or download from external URL"},
            {"method": "PUT", "path": "/api/rest/{slug}", "description": "Update metadata (title, thumbnail, slug) of an existing file"},
            {"method": "DELETE", "path": "/api/rest/{slug}", "description": "Permanently delete a file from Hugging Face dataset"},
            {"method": "GET", "path": "/api/history", "description": "Fetch history of all uploaded files"},
            {"method": "GET", "path": "/api/stats", "description": "Get total files count and storage usage details"}
        ],
        "authentication": {
            "scheme": "Custom Headers & Cookies",
            "header": "password: YOUR_SPACE_PASSWORD",
            "alt": "Or use Browser Cookie: auth_token=YOUR_SPACE_PASSWORD"
        },
        "parameters": {
            "POST_body_FormData": {
                "file": "binary, optional if link_url is provided (Direct Local Upload)",
                "link_url": "string, optional if file is provided (URL to download from)",
                "slug": "string, optional; custom alias for the file url",
                "title": "string, optional; human readable file title",
                "thumbnail": "string (Base64 or URL), optional; custom thumbnail image",
                "media_format": "string, default 'direct'. Set to 'video' or 'audio' to trigger yt-dlp media extraction"
            }
        },
        "behavior": {
            "mediaExtraction": "Automatically uses yt-dlp default terminal mode for YouTube/Insta links when media_format is 'video' or 'audio'.",
            "slugCollision": "409 error when custom slug is already taken.",
            "storage": "Files are stored directly in your private HF Dataset securely.",
            "thumbnails": "Base64 thumbnails are automatically converted and hosted as separate image files."
        },
        "examples": {
            "curlUploadLocalFile": "curl -X POST 'https://your-space.hf.space/api/rest' \\\n  -H 'password: YOUR_SPACE_PASSWORD' \\\n  -F 'file=@/path/to/local/image.jpg' \\\n  -F 'slug=my-custom-image'",
            "curlUploadFromYoutube": "curl -X POST 'https://your-space.hf.space/api/rest' \\\n  -H 'password: YOUR_SPACE_PASSWORD' \\\n  -F 'link_url=https://youtube.com/watch?v=LxPrOsI3Mvw' \\\n  -F 'media_format=video'",
            "fetchJsExample": "const formData = new FormData();\nformData.append('link_url', 'https://example.com/file.zip');\nfetch('https://your-space.hf.space/api/rest', { method: 'POST', headers: { 'password': 'YOUR_SPACE_PASSWORD' }, body: formData }).then(r => r.json());",
            "responseExample": {
                "status": "success",
                "message": "File hosted securely.",
                "metadata": {
                    "slug": "my-custom-image",
                    "filename": "image.jpg",
                    "path": "files/my-custom-image_image.jpg",
                    "title": "image.jpg",
                    "thumbnail": "/f/my-custom-image",
                    "mime_type": "image/jpeg",
                    "size_bytes": 102400,
                    "uploaded_at": "2026-03-31T12:00:00.000Z",
                    "is_external": False,
                    "external_url": ""
                },
                "download_url": "/f/my-custom-image"
            }
        },
        "errors": [
            {"code": 400, "message": "Must provide either a 'file' or 'link_url'"},
            {"code": 401, "message": "UNAUTHORIZED: Access denied. Invalid Master Password"},
            {"code": 404, "message": "File record not found for update or deletion"},
            {"code": 409, "message": "The slug is already assigned to another file"}
        ],
        "docs": "Send a GET request to /api/rest at any time to view this JSON documentation."
    }

url_progress_tracker = {}

@app.post("/api/rest")
async def process_advanced_upload(
    file: UploadFile = File(None),
    link_url: str = Form(None),
    slug: str = Form(None),
    title: str = Form(None),
    thumbnail: str = Form(""),
    format: str = Form("json"),
    chunk_index: int = Form(0),
    total_chunks: int = Form(1),
    upload_id: str = Form(None),
    media_format: str = Form("direct"),
    token: str = Depends(verify_auth)
):
    db = get_db()
    files_list = db.get("files", [])
    
    final_slug = slug.strip() if slug and slug.strip() != "" else str(uuid.uuid4())[:8]
    
    if chunk_index == 0:
        if any(item["slug"] == final_slug for item in files_list):
            raise HTTPException(status_code=409, detail=f"ERROR: The slug '{final_slug}' is already assigned.")

    repo_path = ""
    filename = ""
    file_size = 0
    mime_type = "application/octet-stream"
    is_external = False
    external_url = ""
    extracted_thumb = "" 
    
    # 🌟 FIX: Auto-switcher updated to use 'yt_default' instead of 'video'
    if link_url:
        media_domains = ['youtube.com', 'youtu.be', 'instagram.com', 'twitter.com', 'x.com', 'facebook.com', 'tiktok.com']
        if any(domain in link_url.lower() for domain in media_domains) and media_format == "direct":
            logger.info("Auto-switching to Video Engine for media link.")
            media_format = "yt_default"

    # ==========================================
    # LOGIC 1: UPLOAD FROM URL
    # ==========================================
    if link_url:
        tracker_id = upload_id if upload_id else final_slug
        url_progress_tracker[tracker_id] = {"status": "initializing", "loaded": 0, "total": 0}
        
        try:
            # --- ENGINE A: YT-DLP MEDIA EXTRACTOR ---
            if media_format in ["yt_default", "yt_video", "yt_audio"]:
                def ytdl_progress_hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        url_progress_tracker[tracker_id]["total"] = total
                        url_progress_tracker[tracker_id]["loaded"] = d.get('downloaded_bytes', 0)
                        url_progress_tracker[tracker_id]["status"] = "downloading"
                    elif d['status'] == 'finished':
                        url_progress_tracker[tracker_id]["status"] = "processing_media"

                # Cookie File Injection
                yt_cookies = os.environ.get("YT_COOKIES")
                cookie_path = "/tmp/yt_cookies.txt"
                if yt_cookies:
                    with open(cookie_path, "w") as f:
                        f.write(yt_cookies)

                # 🌟 THE CHROME SPOOFING ENGINE 🌟
                ydl_opts = {
                    'outtmpl': f'/tmp/{final_slug}_media.%(ext)s',
                    'progress_hooks': [ytdl_progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                    },
                    'socket_timeout': 60,
                }

                # Proxy Injection
                proxy_url = os.environ.get("PROXY_URL")
                if proxy_url:
                    ydl_opts['proxy'] = proxy_url
                
                if yt_cookies:
                    ydl_opts['cookiefile'] = cookie_path

                # 🎬 FORMAT LOGIC BASED ON USER UI DROPDOWN
                # --- ENGINE A: YT-DLP MEDIA EXTRACTOR ---
            if media_format in ["yt_default", "yt_video", "yt_audio"]:
                def ytdl_progress_hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        url_progress_tracker[tracker_id]["total"] = total
                        url_progress_tracker[tracker_id]["loaded"] = d.get('downloaded_bytes', 0)
                        url_progress_tracker[tracker_id]["status"] = "downloading"
                    elif d['status'] == 'finished':
                        url_progress_tracker[tracker_id]["status"] = "processing_media"

                # Cookie File Injection
                yt_cookies = os.environ.get("YT_COOKIES")
                cookie_path = "/tmp/yt_cookies.txt"
                if yt_cookies:
                    with open(cookie_path, "w") as f:
                        f.write(yt_cookies)

                # 🌟 NATIVE SPOOFING ENGINE (Let yt-dlp handle it) 🌟
                ydl_opts = {
                    'outtmpl': f'/tmp/{final_slug}_media.%(ext)s',
                    'progress_hooks': [ytdl_progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    # Chrome Headers Hata diye hain.
                    # YouTube ko Web client se bacha kar Android/iOS APIs ke through bypass karenge:
                    'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
                    'socket_timeout': 60,
                }

                # Proxy Injection
                proxy_url = os.environ.get("PROXY_URL")
                if proxy_url:
                    ydl_opts['proxy'] = proxy_url
                
                if yt_cookies:
                    ydl_opts['cookiefile'] = cookie_path

                # 🎬 THE GOD-TIER FORMAT LOGIC
                if media_format == "yt_audio":
                    ydl_opts['format'] = 'ba/bestaudio/best'
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '256',
                    }]
                elif media_format == "yt_video":
                    # Force MP4
                    ydl_opts['format'] = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b'
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    # yt_default (Safest Fallback - No Force MP4)
                    ydl_opts['format'] = 'bv*+ba/b'

                def download_yt():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(link_url, download=True)
                        return info.get('thumbnail'), info.get('title')
                
                extracted_thumb, extracted_title = await asyncio.to_thread(download_yt)
                if extracted_title and not title:
                    title = extracted_title
                
                downloaded_files = glob.glob(f"/tmp/{final_slug}_media.*")
                if not downloaded_files:
                    raise Exception("YT-DLP Failed to generate file.")
                
                temp_path = downloaded_files[0]
                ext = os.path.splitext(temp_path)[1]
                safe_title = "".join(x for x in (title or "Downloaded_Media") if x.isalnum() or x in " _-")
                filename = f"{safe_title[:45]}{ext}"
                
            # --- ENGINE B: STANDARD DIRECT PROXY (Agar YT-DLP OFF ho) ---
            else:
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*'
                }
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(link_url, timeout=45) as r:
                        r.raise_for_status() 
                        
                        cd = r.headers.get('Content-Disposition', '')
                        if 'filename=' in cd:
                            filename = cd.split('filename=')[1].strip('"\' ')
                        else:
                            parsed_url = urllib.parse.urlparse(link_url)
                            filename = os.path.basename(parsed_url.path)
                            if not filename or '.' not in filename:
                                content_type = r.headers.get('Content-Type', '').split(';')[0]
                                ext = mimetypes.guess_extension(content_type) or '.bin'
                                if ext == '.jpe': ext = '.jpg'
                                filename = f"download_{final_slug}{ext}"
                        
                        temp_path = f"/tmp/{final_slug}_{filename}"
                        url_progress_tracker[tracker_id]["total"] = int(r.headers.get('Content-Length', 0))
                        url_progress_tracker[tracker_id]["status"] = "downloading"
                        
                        async with aiofiles.open(temp_path, 'wb') as f:
                            loaded_bytes = 0
                            async for chunk_data in r.content.iter_chunked(1024 * 512): 
                                await f.write(chunk_data)
                                loaded_bytes += len(chunk_data)
                                url_progress_tracker[tracker_id]["loaded"] = loaded_bytes

            # --- COMMON: UPLOAD TO HUGGING FACE ---
            file_size = os.path.getsize(temp_path)
            mime_type, _ = mimetypes.guess_type(temp_path)
            if not mime_type:
                mime_type = "video/mp4" if media_format == "video" else "audio/mpeg"
                
            url_progress_tracker[tracker_id]["status"] = "uploading_to_hf"
            repo_path = f"files/{final_slug}_{filename}"
            
            await asyncio.to_thread(
                api.upload_file, path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset"
            )
            os.remove(temp_path)
            url_progress_tracker[tracker_id]["status"] = "done"
            
        except Exception as e:
            logger.warning(f"Backend URL fetch failed (Falling back to 308): {e}")
            is_external = True
            external_url = link_url
            filename = "External_Media_Link"
            url_progress_tracker[tracker_id]["status"] = "error"

    # ==========================================
    # LOGIC 2: STANDARD / CHUNKED LOCAL FILE UPLOAD
    # ==========================================
    elif file:
        filename = file.filename
        temp_identifier = upload_id if upload_id else final_slug
        temp_path = f"/tmp/{temp_identifier}_{filename}"
        repo_path = f"files/{final_slug}_{filename}"
        
        mode = "ab" if chunk_index > 0 else "wb"
        
        async with aiofiles.open(temp_path, mode) as buffer:
            while chunk_data := await file.read(1024 * 1024):
                await buffer.write(chunk_data)
        
        if chunk_index < total_chunks - 1:
            return {"status": "uploading", "message": f"Chunk {chunk_index + 1}/{total_chunks} received."}
            
        file_size = os.path.getsize(temp_path)
        mime_type, _ = mimetypes.guess_type(temp_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        await asyncio.to_thread(
            api.upload_file, path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset"
        )
        os.remove(temp_path)
        
    else:
        raise HTTPException(status_code=400, detail="Must provide either a 'file' or 'link_url'.")

    # ==========================================
    # 🌟 NEW SMART THUMBNAIL & METADATA LOGIC
    # ==========================================
    final_thumbnail_url = thumbnail
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    
    is_final_step = bool(link_url) or (file and chunk_index == total_chunks - 1)
    
    if is_final_step and thumbnail and thumbnail.startswith("data:image/"):
        try:
            match = re.match(r'data:(image/\w+);base64,(.*)', thumbnail)
            if match:
                img_ext = match.group(1).split('/')[1]
                if img_ext == 'jpeg': img_ext = 'jpg'
                img_data = base64.b64decode(match.group(2))
                
                thumb_filename = f"{final_slug}_thumb.{img_ext}"
                thumb_temp_path = f"/tmp/{thumb_filename}"
                thumb_repo_path = f"files/{thumb_filename}"
                
                with open(thumb_temp_path, "wb") as f:
                    f.write(img_data)
                
                await asyncio.to_thread(
                    api.upload_file, path_or_fileobj=thumb_temp_path, path_in_repo=thumb_repo_path, repo_id=DATASET_REPO, repo_type="dataset"
                )
                os.remove(thumb_temp_path)
                
                final_thumbnail_url = f"/f/{thumb_filename}" 
                
                thumb_record = {
                    "slug": thumb_filename,
                    "filename": f"thumbnail_{final_slug}.{img_ext}",
                    "path": thumb_repo_path,
                    "title": "Auto-Generated Thumbnail",
                    "thumbnail": "",
                    "mime_type": f"image/{img_ext}",
                    "size_bytes": len(img_data),
                    "uploaded_at": upload_timestamp,
                    "is_external": False,
                    "external_url": ""
                }
                files_list.append(thumb_record)

        except Exception as e:
            logger.warning(f"Base64 processing failed: {e}")
            final_thumbnail_url = ""

    if not final_thumbnail_url and mime_type and mime_type.startswith("image/") and not is_external:
        final_thumbnail_url = f"/f/{final_slug}"
        
    if not final_thumbnail_url and extracted_thumb:
        final_thumbnail_url = extracted_thumb

    # ==========================================
    # SAVE MAIN FILE METADATA
    # ==========================================
    file_record = {
        "slug": final_slug,
        "filename": filename,
        "path": repo_path,
        "title": title if title else filename,
        "thumbnail": final_thumbnail_url,
        "mime_type": mime_type,
        "size_bytes": file_size,
        "uploaded_at": upload_timestamp,
        "is_external": is_external,
        "external_url": external_url
    }
    
    files_list.append(file_record)
    db["files"] = files_list
    save_db(db)
    
    if format.lower() == "redirect":
        return RedirectResponse(url=f"/f/{final_slug}", status_code=308)
    
    return {
        "status": "success", 
        "message": "File hosted securely.", 
        "metadata": file_record,
        "download_url": f"/f/{final_slug}"
    }
    
@app.put("/api/rest/{current_slug}")
async def update_file_metadata(
    current_slug: str,
    new_slug: str = Form(None),
    title: str = Form(None),
    thumbnail: str = Form(None),
    token: str = Depends(verify_auth)
):
    db = get_db()
    files_list = db.get("files", [])
    
    for item in files_list:
        if item["slug"] == current_slug:
            if new_slug and new_slug != current_slug:
                if any(x["slug"] == new_slug for x in files_list):
                    raise HTTPException(status_code=409, detail="New slug already exists in database.")
                item["slug"] = new_slug
            
            if title is not None: 
                item["title"] = title
            if thumbnail is not None: 
                item["thumbnail"] = thumbnail
            
            db["files"] = files_list
            save_db(db)
            return {"status": "success", "message": "Metadata updated.", "data": item}
            
    raise HTTPException(status_code=404, detail="File record not found for update.")

@app.delete("/api/rest/{slug}")
async def delete_file_permanently(slug: str, token: str = Depends(verify_auth)):
    db = get_db()
    files_list = db.get("files", [])
    file_record = next((item for item in files_list if item["slug"] == slug), None)
    
    if file_record:
        try:
            api.delete_file(path_in_repo=file_record["path"], repo_id=DATASET_REPO, repo_type="dataset")
        except Exception as e:
            logger.warning(f"File might already be deleted from HF: {e}")
            
        db["files"] = [item for item in files_list if item["slug"] != slug]
        save_db(db)
        return {"status": "success", "message": f"File '{slug}' deleted permanently."}
        
    raise HTTPException(status_code=404, detail="File not found in database.")

@app.get("/api/history")
async def fetch_advanced_history(search: Optional[str] = None, token: str = Depends(verify_auth)):
    db = get_db()
    files_list = db.get("files", [])
    
    if search:
        search_query = search.lower()
        files_list = [f for f in files_list if search_query in f.get("title", "").lower() or search_query in f.get("filename", "").lower()]
        
    for f in files_list:
        if "size_bytes" in f:
            f["formatted_size"] = format_size(f["size_bytes"])
            
    return sorted(files_list, key=lambda x: x.get("uploaded_at", ""), reverse=True)

@app.get("/api/stats")
async def get_server_stats(token: str = Depends(verify_auth)):
    db = get_db()
    total_bytes = db.get("total_size_bytes", 0)
    return {
        "total_files": db.get("total_files", 0),
        "total_size_bytes": total_bytes,
        "formatted_total_size": format_size(total_bytes)
    }

# ==========================================
# 6. PUBLIC CONTENT DELIVERY NETWORK (CDN)
# ==========================================
@app.get("/f/{slug}")
async def serve_file_publicly(slug: str):
    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="404: The requested resource could not be found.")
        
    if file_record.get("is_external") and file_record.get("external_url"):
        return RedirectResponse(url=file_record["external_url"], status_code=308)
        
    try:
        file_path = hf_hub_download(
            repo_id=DATASET_REPO, 
            filename=file_record["path"], 
            repo_type="dataset", 
            token=HF_TOKEN
        )
        return FileResponse(
            path=file_path, 
            filename=file_record["filename"],
            media_type=file_record.get("mime_type", "application/octet-stream"),
            content_disposition_type="inline" 
        )
    except Exception as e:
        logger.error(f"Error serving file '{slug}': {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error while streaming file.")

# ==========================================
# 7. THE MASSIVE HTML / JS DASHBOARD
# ==========================================
@app.post("/api/verify")
async def verify_login_endpoint(token: str = Depends(verify_auth)):
    return {"status": "ok"}

# ==========================================
# 8. SOCIAL MEDIA & QUICK REDIRECTS (308)
# ==========================================
@app.get("/instagram")
async def redirect_instagram():
    return RedirectResponse(url="https://www.instagram.com/deepdey.official", status_code=308)

@app.get("/github")
async def redirect_github():
    return RedirectResponse(url="https://github.com/deepdeyiitgn", status_code=308)

@app.get("/discord")
async def redirect_discord():
    return RedirectResponse(url="https://discord.com/invite/t6ZKNw556n", status_code=308)

@app.get("/youtube")
async def redirect_youtube():
    return RedirectResponse(url="https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/", status_code=308)

@app.get("/wiki")
async def redirect_wiki():
    return RedirectResponse(url="https://qlynk.vercel.app/wiki", status_code=308)

@app.get("/clock")
async def redirect_clock():
    return RedirectResponse(url="https://clock.qlynk.me", status_code=308)

@app.get("/main.js")
async def serve_main_js():
    if os.path.exists("main.js"):
        return FileResponse("main.js", media_type="application/javascript")
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/footer-extras.js")
async def serve_footer_extras_js():
    if os.path.exists("footer-extras.js"):
        return FileResponse("footer-extras.js", media_type="application/javascript")
    raise HTTPException(status_code=404, detail="File not found")    

@app.get("/", response_class=HTMLResponse)
async def serve_frontend_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)