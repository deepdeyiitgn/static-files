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

# Progress Tracking Store
progress_store = {}

def progress_hook(d):
    if d['status'] == 'downloading':
        # yt-dlp automatically filename ko task_id ki tarah use kar sakta hai
        filename = d.get('filename')
        if filename:
            p = d.get('_percent_str', '0%').replace('%','').strip()
            try:
                progress_store[filename] = float(p)
            except:
                pass

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    # Task ID (Slug) ke base par progress return karega
    return {"progress": progress_store.get(task_id, 0)}

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
            # --- ENGINE A: YT-DLP MEDIA EXTRACTOR ---
            # --- ENGINE A: YT-DLP MEDIA EXTRACTOR ---
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

                # Cookie File Setup
                yt_cookies = os.environ.get("YT_COOKIES")
                cookie_path = "/tmp/yt_cookies.txt"
                if yt_cookies:
                    with open(cookie_path, "w") as f:
                        f.write(yt_cookies)

                # 🌟 THE DATACENTER BYPASS ENGINE 🌟
                # 🌟 THE PURE TERMINAL ENGINE (IPv4 Datacenter Fix) 🌟
                ydl_opts = {
                    'outtmpl': f'/tmp/{final_slug}_media.%(ext)s',
                    'progress_hooks': [ytdl_progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'socket_timeout': 60,
                    'force_ipv4': True,  # 👈 YEH RAKHNA HAI (HF ke IPv6 ban hote hain)
                    'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
                    # ❌ Yahan se 'extractor_args' (Smart TV wali line) HATA DI HAI!
                }

                progress_store[final_slug] = 0

                # Proxy Injection
                proxy_url = os.environ.get("PROXY_URL")
                if proxy_url:
                    ydl_opts['proxy'] = proxy_url
                
                # Cookie Injection 
                if yt_cookies:
                    ydl_opts['cookiefile'] = cookie_path

                # 🎬 ZERO-FILTER FORMAT LOGIC
                if media_format == "yt_audio":
                    ydl_opts['format'] = 'bestaudio/best'
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '256',
                    }]
                elif media_format == "yt_video":
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'
                    ydl_opts['merge_output_format'] = 'mp4'
                else:
                    # yt_default: Terminal jaisa same behave karega
                    pass

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

# ==========================================
# 9. VIRTUAL CACHE & DYNAMIC SITEMAP
# ==========================================
import time
from fastapi.responses import Response

# Virtual Cache in-memory store
sitemap_cache = {
    "content": "",
    "last_generated": 0
}

async def generate_sitemap(request: Request):
    try:
        logger.info("Generating Sitemap for cache...")
        
        # Base URL automatically host se nikal lega (e.g., qlynk.me ya HF space link)
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Main routes ke liye current time set kar rahe hain
        current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
        
        urls = []
        
        # 1. Main Page (Priority 1.0)
        urls.append(f"""
        <url>
            <loc>https://static.qlynk.me/</loc>
            <lastmod>{current_time}</lastmod>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>
        """)
        
        # 2. Social & Redirects (Priority 0.7)
        social_links = ["/instagram", "/github", "/discord", "/youtube", "/wiki", "/status", "/clock"]
        for link in social_links:
            urls.append(f"""
            <url>
                <loc>https://static.qlynk.me{link}</loc>
                <lastmod>{current_time}</lastmod>
                <changefreq>weekly</changefreq>
                <priority>0.7</priority>
            </url>
            """)
            
        # 3. Files from history.json (Priority 0.1)
        db = get_db()
        files_list = db.get("files", [])
        for file_record in files_list:
            slug = file_record.get("slug")
            # File ka original upload time use kar raha hai auto-update ke liye
            file_time = file_record.get("uploaded_at", current_time) 
            
            urls.append(f"""
            <url>
                <loc>https://static.qlynk.me/f/{slug}</loc>
                <lastmod>{file_time}</lastmod>
                <changefreq>monthly</changefreq>
                <priority>0.1</priority>
            </url>
            """)
            
        sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {"".join(urls)}
</urlset>"""
        
        sitemap_cache["content"] = sitemap_xml.strip()
        sitemap_cache["last_generated"] = time.time()
        logger.info("Sitemap successfully updated in virtual cache.")
        
    except Exception as e:
        logger.error(f"Error generating sitemap: {e}")

# Background worker jo har 30 minute baad chalega
async def sitemap_updater_loop(request_mock):
    while True:
        await asyncio.sleep(1800)  # 30 mins = 1800 seconds
        await generate_sitemap(request_mock)

@app.get("/sitemap.xml", response_class=Response)
async def serve_sitemap(request: Request):
    # Agar cache khali hai (jaise server just start hua ho)
    if not sitemap_cache["content"]:
        await generate_sitemap(request)
        # Background task sirf tabhi start hogi jab sitemap pehli baar hit ho,
        # isse hum request object ko background loop mein pass kar sakte hain
        asyncio.create_task(sitemap_updater_loop(request))
        
    return Response(content=sitemap_cache["content"], media_type="application/xml")    


# ==========================================
# 10. GOD-MODE DATACENTER TELEMETRY (SECURE & RAW)
# ==========================================
import psutil
import platform
import time
import socket
import logging
import json
import asyncio
import aiohttp
from collections import deque
from fastapi import WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

# --- App Metrics & Memory Stores ---
app_metrics = {
    "req_total": 0, "status_200": 0, "status_4xx": 0, "status_5xx": 0,
    "active_ws": 0, "start_time": time.time()
}
latency_history = deque([0]*20, maxlen=20)

hf_run_logs = deque(maxlen=60)
hf_build_logs = deque(maxlen=60)
server_net_info = {"ip": "Fetching...", "location": "Fetching..."}

# Hardware Info Extractor
def get_deep_hardware_specs():
    info = {"model": platform.processor(), "vendor": "Unknown", "cache": "Unknown", "microcode": "Unknown"}
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line and info["model"] in ["", "Unknown"]:
                    info["model"] = line.split(":")[1].strip()
                elif "vendor_id" in line and info["vendor"] == "Unknown":
                    info["vendor"] = line.split(":")[1].strip()
                elif "cache size" in line and info["cache"] == "Unknown":
                    info["cache"] = line.split(":")[1].strip()
                elif "microcode" in line and info["microcode"] == "Unknown":
                    info["microcode"] = line.split(":")[1].strip()
    except:
        pass
    return info

# Background Async Task to Fetch Server IP Once
async def fetch_server_identity():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://ip-api.com/json/", timeout=5) as resp:
                data = await resp.json()
                server_net_info["ip"] = data.get("query", "Unknown Proxy")
                server_net_info["location"] = f"{data.get('city', '')}, {data.get('country', '')}"
    except:
        server_net_info["ip"] = "Hidden"
        server_net_info["location"] = "HF Datacenter"

# Robust Log Streamer
async def stream_hf_logs(log_type="run", target_deque=hf_run_logs):
    space_id = os.environ.get("SPACE_ID", "deydeep/static-files")
    url = f"https://huggingface.co/api/spaces/{space_id}/logs/{log_type}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    
    while True:
        try:
            if not HF_TOKEN:
                target_deque.appendleft("[SYSTEM] HF_TOKEN missing. Logs locked.")
                await asyncio.sleep(60); continue
                
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=None) as resp:
                    async for line in resp.content:
                        if line:
                            decoded = line.decode('utf-8', errors='ignore').strip()
                            if decoded.startswith('data:'):
                                log_data = decoded[5:].strip()
                                try:
                                    parsed = json.loads(log_data)
                                    msg = parsed.get("message", str(parsed))
                                    target_deque.appendleft(msg)
                                except:
                                    target_deque.appendleft(log_data) # Fallback if not JSON
        except Exception as e:
            await asyncio.sleep(5) 

# API Health Middleware
class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        app_metrics["req_total"] += 1
        try:
            response = await call_next(request)
            if 200 <= response.status_code < 300: app_metrics["status_200"] += 1
            elif 400 <= response.status_code < 500: app_metrics["status_4xx"] += 1
            elif response.status_code >= 500: app_metrics["status_5xx"] += 1
            latency_history.append((time.time() - start_time) * 1000)
            return response
        except Exception as e:
            app_metrics["status_5xx"] += 1
            raise e

app.add_middleware(TelemetryMiddleware)

# --- Virtual HTML payload ---
STATUS_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qlynk Storage Node - Live Telemetry & Status</title>
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://static.qlynk.me/status" />
    
    <link rel="icon" type="image/x-icon" href="//qlynk.vercel.app/favicon.ico" sizes="16x16 32x32">
    <link rel="icon" type="image/png" sizes="16x16" href="//qlynk.vercel.app/quicklink-logo.png">
    <link rel="apple-touch-icon" sizes="180x180" href="//qlynk.vercel.app/quicklink-logo.png">

    <style>
        :root { --bg-color: #0d1117; --card-bg: #161b22; --text-main: #c9d1d9; --text-muted: #8b949e; --accent-green: #2ea043; --accent-blue: #58a6ff; --accent-red: #da3633; --accent-yellow: #d29922; --border: #30363d; }
        body { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace; background-color: var(--bg-color); color: var(--text-main); margin: 0; padding: 20px; font-size: 13px; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 20px; color: #fff; font-family: -apple-system, sans-serif;}
        .badge-container { display: flex; gap: 15px; }
        .badge { background: #1f2428; border: 1px solid var(--border); padding: 5px 12px; border-radius: 6px; display: flex; align-items: center; gap: 8px; }
        .pulse { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); }
        .danger { background-color: var(--accent-red); box-shadow: 0 0 8px var(--accent-red); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 15px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; position: relative; }
        .card h2 { margin: 0 0 15px 0; font-size: 14px; color: var(--accent-blue); text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px dashed #30363d; padding-bottom: 4px; }
        .stat-label { color: var(--text-muted); }
        .stat-val { font-weight: bold; color: #fff; text-align: right; }
        .locked-val { color: var(--accent-red); font-style: italic; font-size: 11px; }
        .bar-bg { width: 100%; background: #000; border-radius: 3px; height: 6px; overflow: hidden; margin-top: 5px; }
        .bar-fill { height: 100%; background: var(--accent-green); width: 0%; transition: width 0.3s ease; }
        .core-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px; }
        .core-box { background: #000; border: 1px solid var(--border); padding: 5px; border-radius: 4px; text-align: center; }
        .core-val { font-size: 11px; margin-top: 3px; color: var(--accent-green); }
        .terminal { background: #000; border: 1px solid var(--border); padding: 10px; border-radius: 6px; height: 350px; overflow-y: auto; font-size: 11px; color: #3fb950; line-height: 1.4; white-space: pre-wrap; word-wrap: break-word;}
        .terminal span.error { color: var(--accent-red); }
        .terminal span.warn { color: var(--accent-yellow); }
        .terminal span.sys { color: var(--accent-blue); }
        .lock-screen { display:flex; justify-content:center; align-items:center; height:100%; color:var(--accent-red); font-weight:bold; font-size:14px; flex-direction:column; gap:10px; text-align:center;}
        .proc-table { width: 100%; text-align: left; border-collapse: collapse; font-size: 11px; }
        .proc-table th { border-bottom: 1px solid var(--border); padding-bottom: 5px; color: var(--text-muted); }
        .proc-table td { padding: 4px 0; border-bottom: 1px dashed #30363d; }
    </style>
</head>
<body>

    <div class="header">
        <h1>⚡ Qlynk Storage Node - Status</h1>
        <div class="badge-container">
            <div class="badge"><div class="pulse" id="ws-pulse"></div> Ping: <span id="ws-ping">...</span>ms</div>
            <div class="badge">Host Uptime: <span id="sys-uptime">...</span></div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>🌍 Network Identity & Identity</h2>
            <div class="stat-row"><span class="stat-label">Server Location</span><span class="stat-val" id="net-loc">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">Server IP Address</span><span class="stat-val" id="net-server-ip">Loading...</span></div>
            <div class="stat-row" style="margin-top:15px;"><span class="stat-label">Your Client IP</span><span class="stat-val" id="net-client-ip" style="color:var(--accent-green);">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">Access Level</span><span class="stat-val" id="net-auth">Verifying...</span></div>
        </div>

        <div class="card">
            <h2>🖧 Deep Hardware Specs</h2>
            <div class="stat-row"><span class="stat-label">CPU Model</span><span class="stat-val" id="spec-model" style="font-size:11px; max-width:65%;">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">CPU Vendor</span><span class="stat-val" id="spec-vendor">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">L-Cache Size</span><span class="stat-val" id="spec-cache">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">Microcode</span><span class="stat-val" id="spec-micro">Loading...</span></div>
            <div class="stat-row"><span class="stat-label">Core Temp</span><span class="stat-val" id="spec-temp" style="color:var(--accent-yellow);">Loading...</span></div>
        </div>

        <div class="card">
            <h2>⚙️ Multi-Core Processing</h2>
            <div class="stat-row"><span class="stat-label">Total System Load</span><span class="stat-val" id="cpu-total">0%</span></div>
            <div class="bar-bg" style="height: 10px; margin-bottom: 15px;"><div class="bar-fill" id="cpu-total-bar" style="background: var(--accent-blue);"></div></div>
            <div class="stat-label" style="font-size: 11px;">Logical Core Threads (<span id="core-count">0</span>)</div>
            <div class="core-grid" id="cpu-cores"></div>
        </div>

        <div class="card">
            <h2>💾 Memory & Storage I/O</h2>
            <div class="stat-row"><span class="stat-label">RAM Usage</span><span class="stat-val" id="ram-txt">0/0 GB</span></div>
            <div class="bar-bg"><div class="bar-fill" id="ram-bar"></div></div>
            <div class="stat-row" style="margin-top: 10px;"><span class="stat-label">Root Disk (/)</span><span class="stat-val" id="disk-txt">0/0 GB</span></div>
            <div class="bar-bg"><div class="bar-fill" id="disk-bar" style="background: var(--accent-blue);"></div></div>
            
            <div class="stat-row" style="margin-top: 15px; color:var(--accent-yellow);"><span class="stat-label">Disk Read Speed</span><span class="stat-val" id="disk-read">0 MB/s</span></div>
            <div class="stat-row" style="color:var(--accent-red);"><span class="stat-label">Disk Write Speed</span><span class="stat-val" id="disk-write">0 MB/s</span></div>
        </div>

        <div class="card">
            <h2>🌐 Network & Cloud Metrics</h2>
            <div class="stat-row"><span class="stat-label">Speed Down ⬇</span><span class="stat-val" id="net-speed-down" style="color: var(--accent-blue);">0 KB/s</span></div>
            <div class="stat-row"><span class="stat-label">Speed Up ⬆</span><span class="stat-val" id="net-speed-up" style="color: var(--accent-green);">0 KB/s</span></div>
            <div class="stat-row" style="margin-top:15px;"><span class="stat-label">Active Connections</span><span class="stat-val" id="net-conn">0</span></div>
            <div class="stat-row" style="margin-top:15px;"><span class="stat-label">HF Storage Used</span><span class="stat-val" id="hf-storage" style="color:var(--accent-yellow);">Loading...</span></div>
        </div>

        <div class="card">
            <h2>🔥 Top 5 Resource Hogs</h2>
            <table class="proc-table" id="proc-table">
                <tr><th>Process Name</th><th>CPU %</th><th>RAM %</th></tr>
                </table>
        </div>

        <div class="card" style="grid-column: span 1;">
            <h2>🚀 Live Container Run Logs</h2>
            <div class="terminal" id="term-run-logs">Waiting for connection...</div>
        </div>
        
        <div class="card" style="grid-column: span 1;">
            <h2>🛠️ Live Image Build Logs</h2>
            <div class="terminal" id="term-build-logs">Waiting for connection...</div>
        </div>
    </div>

    <script>
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/status_max`;
        let ws; let pingStart = 0;

        function formatBytes(bytes) {
            if(bytes === 0) return '0 B';
            const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        function parseLogText(l) {
            let html = l.replace(/</g, "&lt;").replace(/>/g, "&gt;");
            if(html.toLowerCase().includes('error') || html.toLowerCase().includes('traceback') || html.toLowerCase().includes('fail')) return `<span class="error">${html}</span>`;
            if(html.toLowerCase().includes('warn')) return `<span class="warn">${html}</span>`;
            if(html.includes('[SYSTEM]')) return `<span class="sys">${html}</span>`;
            return html;
        }

        function lockText() { return `<span class="locked-val">🔒 HIDDEN (Auth Required)</span>`; }

        function connectWS() {
            ws = new WebSocket(wsUrl);
            ws.onopen = () => {
                document.getElementById('ws-pulse').classList.remove('danger');
                setInterval(() => { if(ws.readyState === WebSocket.OPEN) { pingStart = performance.now(); ws.send("ping"); } }, 2000);
            };

            ws.onmessage = (event) => {
                if(event.data === "pong") { document.getElementById('ws-ping').innerText = Math.round(performance.now() - pingStart); return; }
                const d = JSON.parse(event.data);

                // Auth Logic
                document.getElementById('net-auth').innerHTML = d.auth_valid ? `<span style="color:var(--accent-green);">God Mode (Admin)</span>` : `<span style="color:var(--accent-red);">Guest (Restricted)</span>`;

                // Security / Identity
                document.getElementById('net-loc').innerHTML = d.auth_valid ? d.identity.location : lockText();
                document.getElementById('net-server-ip').innerHTML = d.auth_valid ? d.identity.server_ip : lockText();
                document.getElementById('net-client-ip').innerHTML = d.auth_valid ? d.identity.client_ip : lockText();
                document.getElementById('hf-storage').innerHTML = d.auth_valid ? d.app.hf_storage : lockText();

                // Health & Hardware
                document.getElementById('sys-uptime').innerText = d.sys.host_uptime;
                document.getElementById('spec-model').innerHTML = d.auth_valid ? d.hw.model : lockText();
                document.getElementById('spec-vendor').innerText = d.hw.vendor;
                document.getElementById('spec-cache').innerText = d.hw.cache;
                document.getElementById('spec-micro').innerText = d.hw.microcode;
                document.getElementById('spec-temp').innerText = d.hw.temp;

                // CPU
                document.getElementById('cpu-total').innerText = `${d.cpu.total}%`;
                document.getElementById('cpu-total-bar').style.width = `${d.cpu.total}%`;
                document.getElementById('core-count').innerText = d.cpu.cores.length;
                document.getElementById('cpu-cores').innerHTML = d.cpu.cores.map((c, i) => `<div class="core-box">C${i}<div class="core-val" style="color:${c<60?'#2ea043':c<85?'#d29922':'#da3633'}">${c}%</div></div>`).join('');

                // RAM & Disk
                document.getElementById('ram-txt').innerText = `${d.ram.used_gb} / ${d.ram.total_gb} GB (${d.ram.percent}%)`;
                document.getElementById('ram-bar').style.width = `${d.ram.percent}%`;
                document.getElementById('disk-txt').innerText = `${d.disk.used_gb} / ${d.disk.total_gb} GB (${d.disk.percent}%)`;
                document.getElementById('disk-bar').style.width = `${d.disk.percent}%`;
                
                document.getElementById('disk-read').innerText = formatBytes(d.disk.read_speed) + '/s';
                document.getElementById('disk-write').innerText = formatBytes(d.disk.write_speed) + '/s';

                // Network & Procs
                document.getElementById('net-speed-down').innerText = `${formatBytes(d.net.speed_recv)}/s`;
                document.getElementById('net-speed-up').innerText = `${formatBytes(d.net.speed_sent)}/s`;
                document.getElementById('net-conn').innerText = d.net.active_conns;

                // Top Processes Render
                if(d.auth_valid) {
                    document.getElementById('proc-table').innerHTML = `<tr><th>Process</th><th>CPU %</th><th>RAM %</th></tr>` + 
                        d.procs.map(p => `<tr><td style="color:var(--accent-blue);">${p.name}</td><td>${p.cpu}</td><td>${p.ram}</td></tr>`).join('');
                } else {
                    document.getElementById('proc-table').innerHTML = `<tr><td colspan="3" style="text-align:center; padding:20px;">${lockText()}</td></tr>`;
                }

                // Secure Logs Render
                if (!d.auth_valid) {
                    const lockHtml = `<div class="lock-screen"><span>🔒 ACCESS DENIED</span><span style="color:var(--text-muted); font-weight:normal;">Authenticate via Dashboard to view core logs.</span></div>`;
                    document.getElementById('term-run-logs').innerHTML = lockHtml;
                    document.getElementById('term-build-logs').innerHTML = lockHtml;
                } else {
                    document.getElementById('term-run-logs').innerHTML = d.logs_run.length ? d.logs_run.map(parseLogText).join('<br><br>') : "<i>No run logs yet...</i>";
                    document.getElementById('term-build-logs').innerHTML = d.logs_build.length ? d.logs_build.map(parseLogText).join('<br><br>') : "<i>No build logs yet...</i>";
                }
            };

            ws.onclose = () => {
                document.getElementById('ws-pulse').classList.add('danger');
                document.getElementById('ws-ping').innerText = "DISC";
                setTimeout(connectWS, 3000);
            };
        }
        connectWS();
    </script>
</body>
</html>
"""

def format_uptime(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0: return f"{d}d {h}h {m}m"
    return f"{h}h {m}m {s}s"

# Global task tracker
bg_tasks_started = False

@app.get("/status", response_class=HTMLResponse)
async def serve_max_telemetry():
    global bg_tasks_started
    if not bg_tasks_started:
        asyncio.create_task(stream_hf_logs("run", hf_run_logs))
        asyncio.create_task(stream_hf_logs("build", hf_build_logs))
        asyncio.create_task(fetch_server_identity())
        bg_tasks_started = True
    return HTMLResponse(content=STATUS_DASHBOARD_HTML)

@app.websocket("/ws/status_max")
async def websocket_max_endpoint(websocket: WebSocket):
    await websocket.accept()
    app_metrics["active_ws"] += 1
    
    # 🔒 Authentication Check via Cookie
    auth_cookie = websocket.cookies.get("auth_token", "")
    is_authenticated = (auth_cookie == os.environ.get("SPACE_PASSWORD")) and bool(auth_cookie)
    client_ip = websocket.headers.get("x-forwarded-for", websocket.client.host).split(",")[0]
    
    hw_info = get_deep_hardware_specs()
    prev_net = psutil.net_io_counters()
    prev_disk = psutil.disk_io_counters()
    prev_time = time.time()
    
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if msg == "ping":
                    await websocket.send_text("pong")
                    continue
            except asyncio.TimeoutError:
                pass

            curr_time = time.time()
            curr_net = psutil.net_io_counters()
            curr_disk = psutil.disk_io_counters()
            time_diff = curr_time - prev_time
            
            # Speeds calculation
            speed_recv = max(0, (curr_net.bytes_recv - prev_net.bytes_recv) / time_diff) if time_diff > 0 else 0
            speed_sent = max(0, (curr_net.bytes_sent - prev_net.bytes_sent) / time_diff) if time_diff > 0 else 0
            disk_read_speed = max(0, (curr_disk.read_bytes - prev_disk.read_bytes) / time_diff) if curr_disk and prev_disk and time_diff > 0 else 0
            disk_write_speed = max(0, (curr_disk.write_bytes - prev_disk.write_bytes) / time_diff) if curr_disk and prev_disk and time_diff > 0 else 0
            
            prev_net, prev_disk, prev_time = curr_net, curr_disk, curr_time
            
            # Top 5 Processes (If authenticated)
            top_procs = []
            if is_authenticated:
                procs = []
                for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                    try: procs.append(p.info)
                    except: pass
                # Sort by CPU
                procs = sorted(procs, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
                top_procs = [{"name": p['name'][:15], "cpu": f"{round(p['cpu_percent'] or 0, 1)}%", "ram": f"{round(p['memory_percent'] or 0, 1)}%"} for p in procs]

            # HF Storage Fetch
            hf_used = "Unknown"
            if is_authenticated:
                try:
                    db_local = get_db()
                    hf_used = format_size(db_local.get("total_size_bytes", 0))
                except: pass

            temps = "N/A (Hypervisor Block)"
            if hasattr(psutil, "sensors_temperatures"):
                try:
                    sensor_data = psutil.sensors_temperatures()
                    if sensor_data: temps = f"{list(sensor_data.values())[0][0].current}°C"
                except: pass

            payload = {
                "auth_valid": is_authenticated,
                "identity": {
                    "server_ip": server_net_info["ip"],
                    "location": server_net_info["location"],
                    "client_ip": client_ip
                },
                "sys": {"python": platform.python_version(), "host_uptime": format_uptime(curr_time - psutil.boot_time())},
                "hw": {"model": hw_info["model"], "vendor": hw_info["vendor"], "cache": hw_info["cache"], "microcode": hw_info["microcode"], "temp": temps},
                "cpu": {"total": psutil.cpu_percent(interval=None), "cores": psutil.cpu_percent(interval=None, percpu=True)},
                "ram": {"total_gb": round(psutil.virtual_memory().total/(1024**3), 2), "used_gb": round(psutil.virtual_memory().used/(1024**3), 2), "percent": psutil.virtual_memory().percent},
                "disk": {
                    "total_gb": round(psutil.disk_usage('/').total/(1024**3), 2), "used_gb": round(psutil.disk_usage('/').used/(1024**3), 2), "percent": psutil.disk_usage('/').percent,
                    "read_speed": disk_read_speed, "write_speed": disk_write_speed
                },
                "net": {"total_recv": curr_net.bytes_recv, "total_sent": curr_net.bytes_sent, "speed_recv": speed_recv, "speed_sent": speed_sent, "active_conns": len(psutil.net_connections(kind='inet'))},
                "app": {"hf_storage": hf_used},
                "procs": top_procs,
                "logs_run": list(hf_run_logs) if is_authenticated else [],
                "logs_build": list(hf_build_logs) if is_authenticated else []
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(1) 

    except WebSocketDisconnect:
        app_metrics["active_ws"] -= 1
    except Exception:
        app_metrics["active_ws"] -= 1