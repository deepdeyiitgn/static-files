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
    
@app.put("/api/rest/{current_slug:path}")
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

@app.delete("/api/rest/{slug:path}")
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
# 6. PUBLIC CONTENT DELIVERY NETWORK (CDN) [HONEYPOT ENGINE]
# ==========================================
import random
import os
from fastapi.responses import Response

@app.get("/f/{slug:path}")
async def serve_file_publicly(slug: str):
    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    if not file_record:
        # 🛡️ THE HONEYPOT ENGINE (Anti-Bot / Tarpit)
        # 1. Delay the response artificially to slow down brute-force scripts
        await asyncio.sleep(random.uniform(2.0, 5.0))
        
        # 2. Generate fake corrupted binary data (10KB to 100KB of random garbage)
        fake_size = random.randint(10240, 102400)
        fake_bytes = os.urandom(fake_size)
        
        # 3. Randomize the Content-Type to completely confuse headers filters
        fake_types = ["image/jpeg", "video/mp4", "application/zip", "application/pdf", "audio/mpeg"]
        
        return Response(
            content=fake_bytes, 
            media_type=random.choice(fake_types), 
            status_code=200
        )
        
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
        # Send fake generic binary on 500 error to hide backend failure
        await asyncio.sleep(random.uniform(1.0, 3.0))
        return Response(content=os.urandom(10240), media_type="application/octet-stream", status_code=200)

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
# 10. OMNISCIENT 2.0 TELEMETRY (TITAN-CLASS DATACENTER)
# ==========================================
import psutil
import platform
import time
import socket
import logging
import json
import asyncio
import aiohttp
import subprocess
import math
import statistics
from collections import deque
from fastapi import WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

# --- Global Metrics & Memory Store ---
app_metrics = {
    "req_total": 0, "status_200": 0, "status_4xx": 0, "status_5xx": 0,
    "active_ws": 0, "start_time": time.time()
}

# High-Precision API Tracker
api_latencies = {
    "REST Upload Engine": deque([0.0]*5, maxlen=20),
    "CDN File Stream": deque([0.0]*5, maxlen=20),
    "WebSocket Tunnel": deque([0.0]*5, maxlen=20),
    "Telemetry Node": deque([0.0]*5, maxlen=20),
    "Frontend UI": deque([0.0]*5, maxlen=20),
    "System Backend": deque([0.0]*5, maxlen=20)
}

hf_run_logs = deque(maxlen=200)
hf_build_logs = deque(maxlen=200)

server_net_info = {"ip": "Fetching...", "location": "Fetching...", "isp": "Unknown"}
server_ping_jitter = {"ping": 0.0, "jitter": 0.0, "status": "Checking..."}

# ==========================================
# 🛑 RATE-LIMITING CACHE SYSTEM (HEAVY CALLS)
# ==========================================
# Prevents CPU spikes by caching heavy OS/Network commands
cache_store = {
    "hw": {"data": None, "last_update": 0, "ttl": 3600}, # 1 Hour TTL
    "gpu": {"data": None, "last_update": 0, "ttl": 600}, # 10 Mins TTL
    "hf_quota": {"used": 0, "percent": 0, "avail": 50, "last_update": 0, "ttl": 300} # 5 Mins TTL
}

def get_deep_hardware_specs():
    if time.time() - cache_store["hw"]["last_update"] < cache_store["hw"]["ttl"] and cache_store["hw"]["data"]:
        return cache_store["hw"]["data"]
        
    info = {"model": platform.processor(), "vendor": "Unknown", "cache": "Unknown", "microcode": "Unknown", "os": f"{platform.system()} {platform.release()}"}
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line and info["model"] in ["", "Unknown"]: info["model"] = line.split(":")[1].strip()
                elif "vendor_id" in line and info["vendor"] == "Unknown": info["vendor"] = line.split(":")[1].strip()
                elif "cache size" in line and info["cache"] == "Unknown": info["cache"] = line.split(":")[1].strip()
                elif "microcode" in line and info["microcode"] == "Unknown": info["microcode"] = line.split(":")[1].strip()
    except: pass
    
    cache_store["hw"]["data"] = info
    cache_store["hw"]["last_update"] = time.time()
    return info

def get_gpu_specs():
    if time.time() - cache_store["gpu"]["last_update"] < cache_store["gpu"]["ttl"] and cache_store["gpu"]["data"]:
        return cache_store["gpu"]["data"]
        
    gpu = {"name": "No Dedicated GPU (CPU Compute Only)", "util": "0%", "temp": "N/A", "mem_used": "0", "mem_total": "0"}
    try:
        res = subprocess.check_output(['nvidia-smi', '--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'], text=True)
        if res:
            parts = res.split(',')
            gpu = {"name": parts[0].strip(), "util": f"{parts[1].strip()}%", "temp": f"{parts[2].strip()}°C", "mem_used": parts[3].strip(), "mem_total": parts[4].strip()}
    except: pass
    
    cache_store["gpu"]["data"] = gpu
    cache_store["gpu"]["last_update"] = time.time()
    return gpu

def get_cached_hf_quota():
    if time.time() - cache_store["hf_quota"]["last_update"] < cache_store["hf_quota"]["ttl"]:
        return cache_store["hf_quota"]
        
    limit = 50.00
    try:
        used_val = get_db().get("total_size_bytes", 0)
        hf_gb = used_val / (1024**3)
        cache_store["hf_quota"]["used"] = used_val
        cache_store["hf_quota"]["percent"] = min(100.0, round((hf_gb / limit) * 100, 2))
        cache_store["hf_quota"]["avail"] = max(0.0, round(limit - hf_gb, 2))
    except: pass
    
    cache_store["hf_quota"]["last_update"] = time.time()
    return cache_store["hf_quota"]

# ==========================================
# ASYNC BACKGROUND WORKERS
# ==========================================
async def track_server_network_quality():
    while True:
        try:
            cmd = ["ping", "-c", "3", "8.8.8.8"]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8')
            
            if "avg" in output or "mdev" in output:
                lines = output.split('\n')
                for line in lines:
                    if "rtt" in line or "round-trip" in line:
                        parts = line.split("=")[1].strip().split(" ")[0].split("/")
                        server_ping_jitter["ping"] = round(float(parts[1]), 2)
                        server_ping_jitter["jitter"] = round(float(parts[3]), 2)
                        server_ping_jitter["status"] = "Optimal" if server_ping_jitter["ping"] < 50 else "Stable"
            else:
                server_ping_jitter["status"] = "ICMP Blocked by Host"
        except: server_ping_jitter["status"] = "ICMP Restricted"
        await asyncio.sleep(15) # Run every 15 secs to save CPU

async def fetch_server_identity():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://ip-api.com/json/", timeout=5) as resp:
                data = await resp.json()
                server_net_info["ip"] = data.get("query", "Hidden")
                server_net_info["location"] = f"{data.get('city', '')}, {data.get('country', '')}"
                server_net_info["isp"] = data.get("isp", "Unknown Provider")
    except:
        server_net_info["ip"] = "Hidden Datacenter Hub"
        server_net_info["location"] = "HF Internal Network"

async def stream_hf_logs(log_type="run", target_deque=hf_run_logs):
    space_id = os.environ.get("SPACE_ID", "deydeep/static-files")
    url = f"https://huggingface.co/api/spaces/{space_id}/logs/{log_type}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    
    while True:
        try:
            if not HF_TOKEN:
                target_deque.appendleft("[SYSTEM] Security Lock: HF_TOKEN missing in env.")
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
                                    target_deque.appendleft(parsed.get("message", str(parsed)))
                                except: target_deque.appendleft(log_data)
        except Exception: await asyncio.sleep(5) 

# ==========================================
# HIGH-PRECISION API TELEMETRY MIDDLEWARE
# ==========================================
class TelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # perf_counter is highly accurate for micro-benchmarking
        start_time = time.perf_counter() 
        app_metrics["req_total"] += 1
        path = request.url.path
        
        try:
            response = await call_next(request)
            if 200 <= response.status_code < 300: app_metrics["status_200"] += 1
            elif 400 <= response.status_code < 500: app_metrics["status_4xx"] += 1
            elif response.status_code >= 500: app_metrics["status_5xx"] += 1
            
            latency = (time.perf_counter() - start_time) * 1000
            
            if path.startswith("/api/rest"): api_latencies["REST Upload Engine"].append(latency)
            elif path.startswith("/f/"): api_latencies["CDN File Stream"].append(latency)
            elif path.startswith("/ws"): api_latencies["WebSocket Tunnel"].append(latency)
            elif path.startswith("/status"): api_latencies["Telemetry Node"].append(latency)
            elif path == "/": api_latencies["Frontend UI"].append(latency)
            else: api_latencies["System Backend"].append(latency)
            
            return response
        except Exception as e:
            app_metrics["status_5xx"] += 1
            raise e

app.add_middleware(TelemetryMiddleware)

# ==========================================
# MASSIVE HTML FRONTEND PAYLOAD
# ==========================================
STATUS_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>QLYNK Node Server - Live Status</title>
    <meta name="description" content="God-Mode real-time datacenter monitoring, API matrix latency, multi-core analysis, and live network I/O.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://static.qlynk.me/status" />
    <link rel="icon" type="image/png" href="//qlynk.vercel.app/quicklink-logo.png">
    
    <!-- Dependencies for UI & PDF Export -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

    <style>
        :root { --bg-color: #0d1117; --card-bg: #161b22; --text-main: #c9d1d9; --text-muted: #8b949e; --accent-green: #2ea043; --accent-blue: #58a6ff; --accent-red: #da3633; --accent-yellow: #d29922; --border: #30363d; --accent-purple: #bc8cff;}
        * { box-sizing: border-box; }
        body { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace; background-color: var(--bg-color); color: var(--text-main); margin: 0; padding: 20px; font-size: 13px; overflow-x: hidden;}
        
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;}
        .header h1 { margin: 0; font-size: 22px; color: #fff; font-family: -apple-system, sans-serif;}
        .badge-container { display: flex; gap: 10px; flex-wrap: wrap;}
        .badge { background: #1f2428; border: 1px solid var(--border); padding: 6px 12px; border-radius: 6px; display: flex; align-items: center; gap: 8px; font-weight: bold;}
        .pulse { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); }
        .danger { background-color: var(--accent-red); box-shadow: 0 0 8px var(--accent-red); }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 15px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; position: relative; display: flex; flex-direction: column;}
        .card h2 { margin: 0 0 15px 0; font-size: 14px; color: var(--accent-blue); text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--border); padding-bottom: 8px; display: flex; justify-content: space-between;}
        
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px dashed #30363d; padding-bottom: 4px; align-items: center;}
        .stat-label { color: var(--text-muted); }
        .stat-val { font-weight: bold; color: #fff; text-align: right; }
        .locked-val { color: var(--accent-red); font-style: italic; font-size: 11px; }
        
        .bar-bg { width: 100%; background: #000; border-radius: 3px; height: 6px; overflow: hidden; margin-top: 5px; }
        .bar-fill { height: 100%; background: var(--accent-green); width: 0%; transition: width 0.3s ease; }
        
        .core-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(75px, 1fr)); gap: 6px; margin-top: 10px; }
        .core-box { background: #000; border: 1px solid var(--border); padding: 5px; border-radius: 4px; text-align: center; }
        .core-val { font-size: 11px; margin-top: 3px; font-weight:bold;}
        .core-meta { font-size: 9px; color: var(--text-muted); }
        
        .terminal { background: #000; border: 1px solid var(--border); padding: 12px; border-radius: 6px; height: 400px; overflow-y: auto; font-size: 12px; color: #3fb950; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; font-family: monospace;}
        .terminal span.error { color: var(--accent-red); font-weight: bold;}
        .terminal span.warn { color: var(--accent-yellow); }
        .terminal span.sys { color: var(--accent-blue); }
        
        .proc-table { width: 100%; text-align: left; border-collapse: collapse; font-size: 11px; margin-top: auto;}
        .proc-table th { border-bottom: 1px solid var(--border); padding-bottom: 5px; color: var(--text-muted); }
        .proc-table td { padding: 4px 0; border-bottom: 1px dashed #30363d; }
        .full-width { grid-column: 1 / -1; } 
        
        .condition-badge { display:inline-block; padding: 4px 8px; border-radius: 4px; font-size:11px; font-weight:bold; margin-top:5px; border: 1px solid var(--border); background: #000;}
        
        /* Export Buttons Matrix */
        .export-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        .btn { padding: 10px; border: 1px solid var(--border); background: #1f2428; color: #fff; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; transition: 0.2s; text-align: center; text-transform: uppercase;}
        .btn:hover { background: var(--accent-blue); color: #000; border-color: var(--accent-blue); }
        .btn-pdf { background: var(--accent-red); color: #fff; border-color: var(--accent-red); }
        .btn-pdf:hover { background: #ff5c5c; border-color: #ff5c5c;}
        
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .header { flex-direction: column; align-items: flex-start; }
            .badge-container { width: 100%; justify-content: space-between; }
            .terminal { height: 300px; }
            body { padding: 10px; }
        }
    </style>
</head>
<body>
    <div id="pdf-container">
        <div class="header">
            <h1>👁️ QLYNK Node Hosting - Status Page</h1>
            <div class="badge-container">
                <div class="badge">App Engine: <span id="app-uptime" style="color:var(--accent-blue); margin-left:5px;">...</span></div>
                <div class="badge">Host System: <span id="sys-uptime" style="color:var(--accent-purple); margin-left:5px;">...</span></div>
            </div>
        </div>

        <div class="grid">
            <!-- Client & Route Analytics -->
            <div class="card">
                <h2>🌍 Link Identity & Route Analytics</h2>
                <div class="stat-row"><span class="stat-label">Datacenter Region</span><span class="stat-val" id="net-loc">Loading...</span></div>
                <div class="stat-row"><span class="stat-label">Server IPv4</span><span class="stat-val" id="net-server-ip">Loading...</span></div>
                <div class="stat-row" style="margin-top:10px;"><span class="stat-label">Your Client IP</span><span class="stat-val" id="net-client-ip" style="color:var(--accent-purple);">Loading...</span></div>
                
                <div class="stat-row" style="margin-top:10px; border-top:1px dashed #30363d; padding-top:10px;">
                    <span class="stat-label" style="color:var(--accent-blue);">Client D/L Throughput</span>
                    <span class="stat-val" id="client-dl-speed">0 KB/s</span>
                </div>
                <div class="stat-row"><span class="stat-label" style="color:var(--accent-green);">Client U/L Throughput</span><span class="stat-val" id="client-ul-speed">0 KB/s</span></div>
                
                <div class="stat-row"><span class="stat-label">Client Ping & Jitter</span><span class="stat-val"><span id="ws-ping">0</span> ms | <span id="ws-jitter" style="color:var(--accent-yellow);">0</span> ms</span></div>
                <div style="text-align:right;"><span id="client-condition" class="condition-badge">Analyzing Route...</span></div>
            </div>

            <!-- Deep HW Specs -->
            <div class="card">
                <h2>🖧 System Postmortem (HW)</h2>
                <div class="stat-row"><span class="stat-label">Operating System</span><span class="stat-val" id="spec-os">Loading...</span></div>
                <div class="stat-row"><span class="stat-label">CPU Module</span><span class="stat-val" id="spec-model" style="font-size:10px; max-width:65%;">Loading...</span></div>
                <div class="stat-row"><span class="stat-label">Cache / Context SW</span><span class="stat-val" id="spec-cache">Loading...</span></div>
                
                <div class="stat-row" style="margin-top:15px;"><span class="stat-label">GPU Interface</span><span class="stat-val" id="gpu-model" style="color:var(--accent-purple); font-size:10px;">Loading...</span></div>
                <div class="stat-row"><span class="stat-label">GPU Memory / Temp</span><span class="stat-val" id="gpu-stats">Loading...</span></div>
            </div>

            <!-- Core-by-Core Engine -->
            <div class="card" style="grid-column: span 1;">
                <h2>⚙️ Core-by-Core Analytics</h2>
                <div class="stat-row"><span class="stat-label">Master CPU Load</span><span class="stat-val" id="cpu-total">0%</span></div>
                <div class="bar-bg" style="height: 10px; margin-bottom: 10px;"><div class="bar-fill" id="cpu-total-bar" style="background: var(--accent-blue);"></div></div>
                <div class="stat-label" style="font-size: 11px;">Active Core Threads: <span id="core-count" style="color:var(--accent-green); font-weight:bold;">0</span> (Freq MHz)</div>
                <div class="core-grid" id="cpu-cores"></div>
            </div>

            <!-- Datacenter Memory & Cloud -->
            <div class="card">
                <h2>☁️ Storage Node Matrix</h2>
                <div class="stat-row"><span class="stat-label">RAM Pool</span><span class="stat-val" id="ram-txt">0/0 GB</span></div>
                <div class="bar-bg"><div class="bar-fill" id="ram-bar"></div></div>
                
                <div class="stat-row" style="margin-top: 15px;"><span class="stat-label" id="hf-label">HF Cloud Quota (Limit)</span><span class="stat-val" id="hf-txt">0/0 GB</span></div>
                <div class="bar-bg"><div class="bar-fill" id="hf-bar" style="background: var(--accent-purple);"></div></div>
                <div class="stat-row"><span class="stat-label" style="font-size:10px;">Available Cloud Block</span><span class="stat-val" id="hf-avail" style="font-size:10px; color:var(--accent-green);">0 GB</span></div>

                <div class="stat-row" style="margin-top: 15px; color:var(--accent-yellow);"><span class="stat-label">Host Disk Read (I/O)</span><span class="stat-val" id="disk-read">0 MB/s</span></div>
                <div class="stat-row" style="color:var(--accent-red);"><span class="stat-label">Host Disk Write (I/O)</span><span class="stat-val" id="disk-write">0 MB/s</span></div>
            </div>

            <!-- Server Network Status -->
            <div class="card">
                <h2>📡 Server Outbound & Inbound</h2>
                <div class="stat-row"><span class="stat-label" style="color:var(--accent-blue);">Server Downlink ⬇</span><span class="stat-val" id="net-speed-down">0 KB/s</span></div>
                <div class="stat-row"><span class="stat-label" style="color:var(--accent-green);">Server Uplink ⬆</span><span class="stat-val" id="net-speed-up">0 KB/s</span></div>
                <div class="stat-row" style="margin-top:15px;"><span class="stat-label">Total Outbound Array</span><span class="stat-val" id="net-sent-total">0 GB</span></div>
                <div class="stat-row"><span class="stat-label">ISP / Datacenter</span><span class="stat-val" id="net-isp">Loading...</span></div>
                <div class="stat-row"><span class="stat-label">Server Ping & Jitter</span><span class="stat-val"><span id="svr-ping">0</span> ms | <span id="svr-jitter" style="color:var(--accent-yellow);">0</span> ms</span></div>
            </div>

            <!-- API Postmortem -->
            <div class="card">
                <h2>🚦 Microservices Latency (API)</h2>
                <div style="display:flex; justify-content:space-between; color:var(--text-muted); font-size:10px; margin-bottom:5px; border-bottom:1px solid var(--border); padding-bottom:5px;">
                    <span>ENDPOINT SUBSYSTEM</span><span>AVG LATENCY (MS)</span>
                </div>
                <div id="api-latencies"></div>
                <div class="stat-row" style="margin-top:10px; border-top:1px dashed var(--border); padding-top:10px;">
                    <span class="stat-label">Total Handled Requests</span><span class="stat-val" id="req-total" style="color:var(--accent-blue);">0</span>
                </div>
            </div>

            <!-- Processes Table -->
            <div class="card">
                <h2>🔥 Priority Process Load</h2>
                <table class="proc-table" id="proc-table">
                    <tr><th>Process Matrix</th><th>CPU %</th><th>RAM %</th></tr>
                </table>
            </div>

            <!-- Data Export Subsystem -->
            <div class="card">
                <h2>💾 Omniscient Export Engine</h2>
                <p style="font-size:11px; color:var(--text-muted); margin-bottom:10px;">Extract precise telemetry data locally. Print function removed in favor of direct PDF generation.</p>
                <div class="export-grid">
                    <div class="btn btn-pdf" onclick="exportPDF()">Download PDF</div>
                    <div class="btn" onclick="exportJSON()">Extract JSON</div>
                    <div class="btn" onclick="exportMD()">Extract Markdown</div>
                    <div class="btn" onclick="exportPNG()">Matrix Snapshot</div>
                </div>
            </div>
            
            <!-- Terminal Logs -->
            <div class="card full-width">
                <h2>🚀 Live Container Run Output (System)</h2>
                <div class="terminal" id="term-run-logs">Establishing Secure Connection...</div>
            </div>
            
            <div class="card full-width">
                <h2>🛠️ Live Image Build Output (Dependency)</h2>
                <div class="terminal" id="term-build-logs">Establishing Secure Connection...</div>
            </div>
        </div>
    </div>

    <script>
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/status_max`;
        let ws; 
        
        // Advanced Client Network Math
        let pingStart = 0; 
        let pingHistory = [];
        let clientBytesRecv = 0; let lastClientTime = performance.now();
        let lastPayload = null;

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
        function lockText() { return `<span class="locked-val">🔒 LOCKED (Auth Req)</span>`; }

        function connectWS() {
            ws = new WebSocket(wsUrl);
            ws.onopen = () => {
                document.getElementById('ws-pulse').classList.remove('danger');
                // Ping to calculate Client-side network states
                setInterval(() => { if(ws.readyState === WebSocket.OPEN) { pingStart = performance.now(); ws.send("ping"); } }, 2000);
            };

            ws.onmessage = (event) => {
                // Client Speeds Check
                let payloadSize = new Blob([event.data]).size;
                clientBytesRecv += payloadSize;
                
                let now = performance.now();
                let timeDiffClient = (now - lastClientTime) / 1000;
                if(timeDiffClient >= 1) {
                    let dlSpeed = clientBytesRecv / timeDiffClient;
                    document.getElementById('client-dl-speed').innerText = formatBytes(dlSpeed) + "/s";
                    document.getElementById('client-ul-speed').innerText = formatBytes(payloadSize/4) + "/s"; // Simulated UL throughput based on WS pings
                    clientBytesRecv = 0; lastClientTime = now;
                }

                if(event.data === "pong") { 
                    let latency = Math.round(performance.now() - pingStart);
                    pingHistory.push(latency);
                    if(pingHistory.length > 10) pingHistory.shift();
                    
                    let jitter = 0;
                    if(pingHistory.length > 1) {
                        let diffs = [];
                        for(let i=1; i<pingHistory.length; i++) diffs.push(Math.abs(pingHistory[i] - pingHistory[i-1]));
                        jitter = Math.round(diffs.reduce((a,b)=>a+b,0) / diffs.length);
                    }
                    
                    document.getElementById('ws-ping').innerText = latency; 
                    document.getElementById('ws-jitter').innerText = jitter;
                    
                    let condEl = document.getElementById('client-condition');
                    if(latency < 100 && jitter < 20) {
                        condEl.innerText = "🚀 Optimal Route"; condEl.style.color = "var(--accent-green)"; condEl.style.borderColor = "var(--accent-green)";
                    } else if (latency < 300) {
                        condEl.innerText = "⚠️ Stable Route"; condEl.style.color = "var(--accent-yellow)"; condEl.style.borderColor = "var(--accent-yellow)";
                    } else {
                        condEl.innerText = "🐢 Poor Route"; condEl.style.color = "var(--accent-red)"; condEl.style.borderColor = "var(--accent-red)";
                    }
                    return; 
                }
                
                const d = JSON.parse(event.data);
                lastPayload = d; 

                // Network & Identity
                document.getElementById('net-loc').innerHTML = d.auth_valid ? d.identity.location : lockText();
                document.getElementById('net-server-ip').innerHTML = d.auth_valid ? d.identity.server_ip : lockText();
                document.getElementById('net-isp').innerHTML = d.auth_valid ? d.identity.isp : lockText();
                document.getElementById('net-client-ip').innerHTML = d.auth_valid ? d.identity.client_ip : lockText();

                // Core Engine HW
                document.getElementById('app-uptime').innerText = d.sys.app_uptime;
                document.getElementById('sys-uptime').innerText = d.sys.host_uptime;
                document.getElementById('spec-os').innerText = d.hw.os;
                document.getElementById('spec-model').innerHTML = d.auth_valid ? d.hw.model : lockText();
                document.getElementById('spec-cache').innerHTML = d.auth_valid ? `${d.hw.cache} / ${d.sys.ctx_switches} CtxSW` : lockText();
                
                document.getElementById('gpu-model').innerHTML = d.auth_valid ? d.hw.gpu.name : lockText();
                document.getElementById('gpu-stats').innerHTML = d.auth_valid ? `${d.hw.gpu.mem_used}MB / ${d.hw.gpu.mem_total}MB | ${d.hw.gpu.temp}` : lockText();

                document.getElementById('cpu-total').innerText = `${d.cpu.total}%`;
                document.getElementById('cpu-total-bar').style.width = `${d.cpu.total}%`;
                document.getElementById('core-count').innerText = d.cpu.cores.length;
                document.getElementById('cpu-cores').innerHTML = d.cpu.cores.map((c, i) => {
                    let freq = d.cpu.freqs[i] ? `${Math.round(d.cpu.freqs[i])}` : 'Lock';
                    return `<div class="core-box">
                        <div style="font-size:10px; color:#fff;">T-${i}</div>
                        <div class="core-val" style="color:${c<60?'#2ea043':c<85?'#d29922':'#da3633'}">${c}%</div>
                        <div class="core-meta">${freq}</div>
                    </div>`;
                }).join('');

                // Memory / Quotas / Disk
                document.getElementById('ram-txt').innerText = `${d.ram.used_gb} / ${d.ram.total_gb} GB (${d.ram.percent}%)`;
                document.getElementById('ram-bar').style.width = `${d.ram.percent}%`;
                
                document.getElementById('hf-label').innerText = `HF Quota (Limit: ${d.app.hf_limit}GB)`;
                document.getElementById('hf-txt').innerHTML = d.auth_valid ? `${d.app.hf_used} / ${d.app.hf_limit} GB (${d.app.hf_percent}%)` : lockText();
                document.getElementById('hf-bar').style.width = d.auth_valid ? `${d.app.hf_percent}%` : '0%';
                document.getElementById('hf-avail').innerHTML = d.auth_valid ? `${d.app.hf_avail} GB Block` : lockText();

                document.getElementById('disk-read').innerText = formatBytes(d.disk.read_speed) + '/s';
                document.getElementById('disk-write').innerText = formatBytes(d.disk.write_speed) + '/s';

                // Server Transport
                document.getElementById('net-speed-down').innerText = `${formatBytes(d.net.speed_recv)}/s`;
                document.getElementById('net-speed-up').innerText = `${formatBytes(d.net.speed_sent)}/s`;
                document.getElementById('net-sent-total').innerText = formatBytes(d.net.total_sent);
                document.getElementById('svr-ping').innerText = d.net.server_ping;
                document.getElementById('svr-jitter').innerText = d.net.server_jitter;

                // API Matrix
                document.getElementById('api-latencies').innerHTML = Object.entries(d.app.api_speeds).map(([k,v]) => {
                    let c = v < 100 ? 'var(--accent-green)' : (v < 300 ? 'var(--accent-yellow)' : 'var(--accent-red)');
                    return `<div class="stat-row" style="margin-bottom:4px;"><span class="stat-label">${k}</span><span class="stat-val" style="color:${c}">${v.toFixed(2)} ms</span></div>`;
                }).join('');
                document.getElementById('req-total').innerText = d.app.req_total;

                // Top Matrix Processes
                if(d.auth_valid) {
                    document.getElementById('proc-table').innerHTML = `<tr><th>Process Matrix</th><th>CPU %</th><th>RAM %</th></tr>` + 
                        d.procs.map(p => `<tr><td style="color:var(--accent-blue);">${p.name}</td><td>${p.cpu}</td><td>${p.ram}</td></tr>`).join('');
                } else { document.getElementById('proc-table').innerHTML = `<tr><td colspan="3" style="text-align:center; padding:20px;">${lockText()}</td></tr>`; }

                // Massive Terminal Interception
                if (!d.auth_valid) {
                    const lockHtml = `<div class="lock-screen" style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--accent-red); font-size:16px;">🔒 OMNISCIENT LOCK: Enter Datacenter Password in Root UI.</div>`;
                    document.getElementById('term-run-logs').innerHTML = lockHtml;
                    document.getElementById('term-build-logs').innerHTML = lockHtml;
                } else {
                    document.getElementById('term-run-logs').innerHTML = d.logs_run.length ? d.logs_run.map(parseLogText).join('<br>') : "<i>No run logs...</i>";
                    document.getElementById('term-build-logs').innerHTML = d.logs_build.length ? d.logs_build.map(parseLogText).join('<br>') : "<i>No build logs...</i>";
                }
            };

            ws.onclose = () => {
                document.getElementById('ws-pulse').classList.add('danger');
                document.getElementById('ws-ping').innerText = "DISC";
                document.getElementById('client-condition').innerText = "Connection Broken";
                setTimeout(connectWS, 3000);
            };
        }
        connectWS();

        // --- Export Master Subsystem ---
        function triggerDownload(content, filename, type) {
            const blob = new Blob([content], { type: type });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
        }

        function exportJSON() {
            if(!lastPayload) return alert("Waiting for matrix data...");
            triggerDownload(JSON.stringify(lastPayload, null, 4), `Omniscient_Telemetry_${new Date().getTime()}.json`, 'application/json');
        }

        function exportMD() {
            if(!lastPayload) return alert("Waiting for data...");
            let md = `# Omniscient Node Telemetry\n*Generated: ${new Date().toISOString()}*\n\n`;
            md += `## Host Core\n- **OS:** ${lastPayload.sys.os}\n- **Uptime:** ${lastPayload.sys.app_uptime}\n- **Processor:** ${lastPayload.hw.model}\n\n`;
            md += `## Cloud Quotas\n- **RAM Engine:** ${lastPayload.ram.used_gb}/${lastPayload.ram.total_gb} GB\n- **HF Max Bounds:** ${lastPayload.app.hf_limit} GB\n\n`;
            md += `## API Postmortem\n`;
            for(let [k,v] of Object.entries(lastPayload.app.api_speeds)) md += `- **${k}:** ${v.toFixed(2)}ms\n`;
            triggerDownload(md, `Omniscient_Telemetry_${new Date().getTime()}.md`, 'text/markdown');
        }

        function exportPDF() {
            const element = document.getElementById('pdf-container');
            const opt = {
                margin: 0.2,
                filename: `Omniscient_Telemetry_${new Date().getTime()}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, logging: false, backgroundColor: '#0d1117' },
                jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' }
            };
            // Hide heavy logs during PDF generation to prevent cut-offs
            document.querySelectorAll('.full-width').forEach(e => e.style.display = 'none');
            html2pdf().set(opt).from(element).save().then(() => {
                document.querySelectorAll('.full-width').forEach(e => e.style.display = 'flex');
            });
        }

        function exportPNG() {
            if(typeof html2canvas === 'undefined') return alert("Canvas Core Loading...");
            document.querySelectorAll('.full-width').forEach(e => e.style.display = 'none');
            html2canvas(document.getElementById('pdf-container'), { backgroundColor: '#0d1117' }).then(canvas => {
                document.querySelectorAll('.full-width').forEach(e => e.style.display = 'flex');
                const a = document.createElement('a');
                a.href = canvas.toDataURL("image/png");
                a.download = `Omniscient_Matrix_${new Date().getTime()}.png`;
                a.click();
            });
        }
    </script>
</body>
</html>
"""

def format_uptime(seconds):
    m, s = divmod(int(seconds), 60); h, m = divmod(m, 60); d, h = divmod(h, 24)
    if d > 0: return f"{d}d {h}h {m}m"
    return f"{h}h {m}m {s}s"

bg_tasks_started = False

@app.get("/status", response_class=HTMLResponse)
async def serve_max_telemetry():
    global bg_tasks_started
    if not bg_tasks_started:
        asyncio.create_task(stream_hf_logs("run", hf_run_logs))
        asyncio.create_task(stream_hf_logs("build", hf_build_logs))
        asyncio.create_task(fetch_server_identity())
        asyncio.create_task(track_server_network_quality())
        bg_tasks_started = True
    return HTMLResponse(content=STATUS_DASHBOARD_HTML)

@app.websocket("/ws/status_max")
async def websocket_max_endpoint(websocket: WebSocket):
    await websocket.accept()
    app_metrics["active_ws"] += 1
    
    auth_cookie = websocket.cookies.get("auth_token", "")
    is_authenticated = (auth_cookie == os.environ.get("SPACE_PASSWORD")) and bool(auth_cookie)
    client_ip = websocket.headers.get("x-forwarded-for", websocket.client.host).split(",")[0]
    
    prev_net = psutil.net_io_counters()
    prev_disk = psutil.disk_io_counters()
    prev_time = time.time()
    
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if msg == "ping": await websocket.send_text("pong"); continue
            except asyncio.TimeoutError: pass

            curr_time = time.time()
            curr_net = psutil.net_io_counters()
            curr_disk = psutil.disk_io_counters()
            time_diff = curr_time - prev_time
            
            # True I/O Extractor
            speed_recv = max(0, (curr_net.bytes_recv - prev_net.bytes_recv) / time_diff) if time_diff > 0 else 0
            speed_sent = max(0, (curr_net.bytes_sent - prev_net.bytes_sent) / time_diff) if time_diff > 0 else 0
            disk_read_speed = max(0, (curr_disk.read_bytes - prev_disk.read_bytes) / time_diff) if curr_disk and prev_disk and time_diff > 0 else 0
            disk_write_speed = max(0, (curr_disk.write_bytes - prev_disk.write_bytes) / time_diff) if curr_disk and prev_disk and time_diff > 0 else 0
            prev_net, prev_disk, prev_time = curr_net, curr_disk, curr_time
            
            # Rate-Limited Cached Hardware Extractions
            hw_info = get_deep_hardware_specs()
            gpu_info = get_gpu_specs()
            hf_quota = get_cached_hf_quota()
            
            # System Counters (Context switches)
            ctx_switches = 0
            try: ctx_switches = psutil.cpu_stats().ctx_switches
            except: pass

            # Top Processes Search
            top_procs = []
            if is_authenticated:
                procs = []
                for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                    try: procs.append(p.info)
                    except: pass
                procs = sorted(procs, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
                top_procs = [{"name": p['name'][:15], "cpu": f"{round(p['cpu_percent'] or 0, 1)}%", "ram": f"{round(p['memory_percent'] or 0, 1)}%"} for p in procs]

            # High-Precision API Latency Calculation
            avg_apis = {}
            for k, q in api_latencies.items():
                valid_latencies = [val for val in q if val > 0]
                avg_apis[k] = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 0.0

            # Dynamic Frequencies
            cpu_freqs = []
            try:
                freqs = psutil.cpu_freq(percpu=True)
                if freqs: cpu_freqs = [f.current for f in freqs]
            except: pass

            payload = {
                "auth_valid": is_authenticated,
                "identity": {"server_ip": server_net_info["ip"], "location": server_net_info["location"], "isp": server_net_info["isp"], "client_ip": client_ip},
                "sys": {"os": hw_info["os"], "app_uptime": format_uptime(curr_time - app_metrics["start_time"]), "host_uptime": format_uptime(curr_time - psutil.boot_time()), "ctx_switches": ctx_switches},
                "hw": {"model": hw_info["model"], "vendor": hw_info["vendor"], "cache": hw_info["cache"], "microcode": hw_info["microcode"], "gpu": gpu_info},
                "cpu": {"total": psutil.cpu_percent(interval=None), "cores": psutil.cpu_percent(interval=None, percpu=True), "freqs": cpu_freqs},
                "ram": {"total_gb": round(psutil.virtual_memory().total/(1024**3), 2), "used_gb": round(psutil.virtual_memory().used/(1024**3), 2), "percent": psutil.virtual_memory().percent},
                "disk": {"read_speed": disk_read_speed, "write_speed": disk_write_speed},
                "net": {"speed_recv": speed_recv, "speed_sent": speed_sent, "total_sent": curr_net.bytes_sent, "server_ping": server_ping_jitter["ping"], "server_jitter": server_ping_jitter["jitter"]},
                "app": {"hf_used": format_size(hf_quota["used"]), "hf_percent": hf_quota["percent"], "hf_avail": hf_quota["avail"], "hf_limit": 50.00, "api_speeds": avg_apis, "req_total": app_metrics["req_total"]},
                "procs": top_procs,
                "logs_run": list(hf_run_logs) if is_authenticated else [],
                "logs_build": list(hf_build_logs) if is_authenticated else []
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(1) 

    except WebSocketDisconnect: app_metrics["active_ws"] -= 1
    except Exception: app_metrics["active_ws"] -= 1

# ==========================================
# 11. QLYNK MEDIA TUBE (CINEMATIC VAULT, CUSTOM PLAYER & CC)
# ==========================================
from fastapi import Query, Header, Cookie, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from typing import Dict, Any
import time
import uuid
import json
import os
from datetime import datetime
from huggingface_hub import hf_hub_download # Assuming these are imported globally in your actual file

# --- 🧠 In-Memory Token Store & Subtitle DB Managers ---
share_tokens_store = {} 

def get_sub_db() -> Dict[str, Any]:
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history_subtitle.json", repo_type="dataset", token=HF_TOKEN)
        with open(file_path, "r") as f:
            return json.load(f)
    except:
        return {"subtitles": []}

def save_sub_db(db_data: Dict[str, Any]):
    with open("history_subtitle.json", "w") as f:
        json.dump(db_data, f, indent=4)
    api.upload_file(path_or_fileobj="history_subtitle.json", path_in_repo="history_subtitle.json", repo_id=DATASET_REPO, repo_type="dataset")

# --- 🔒 Dual-Auth Verifier ---
def verify_view_access(password: str = Header(None), auth_token: str = Cookie(None), share_token: str = Cookie(None)):
    admin_token = password or auth_token
    if admin_token and admin_token == SPACE_PASSWORD:
        return {"role": "admin"}
    if share_token:
        expiry = share_tokens_store.get(share_token)
        if expiry and time.time() < expiry:
            return {"role": "guest"}
        elif expiry:
            del share_tokens_store[share_token] 
    raise HTTPException(status_code=401, detail="Access Expired or Denied.")

# --- 🔗 Share Token API ---
@app.post("/api/share/generate")
async def generate_share_token(token: str = Depends(verify_auth)):
    new_token = uuid.uuid4().hex
    share_tokens_store[new_token] = time.time() + 86400  # 24 Hours expiry
    return {"status": "success", "share_token": new_token}

# --- 📁 Media Library API ---
@app.get("/api/media_library")
async def fetch_media_library(access: dict = Depends(verify_view_access)):
    db = get_db()
    # Filter for videos and audios only
    filtered_files = [
        f for f in db.get("files", []) 
        if not f.get("is_external") and str(f.get("mime_type", "")).startswith(("video/", "audio/"))
    ]
    return sorted(filtered_files, key=lambda x: x.get("uploaded_at", ""), reverse=True)

# --- 📝 Subtitle Upload API ---
@app.post("/api/subtitle/upload")
async def upload_subtitle(
    file: UploadFile = File(...),
    media_slug: str = Form(...),
    language: str = Form(...),
    token: str = Depends(verify_auth)
):
    content = (await file.read()).decode('utf-8', errors='ignore')
    
    # Auto Convert SRT to WebVTT
    if file.filename.endswith('.srt') or not content.startswith('WEBVTT'):
        content = "WEBVTT\n\n" + content.replace(',', '.')
        
    sub_slug = str(uuid.uuid4())[:8]
    filename = f"{language.lower()}_{sub_slug}.vtt"
    temp_path = f"/tmp/{filename}"
    repo_path = f"subtitles/{filename}"
    
    with open(temp_path, "w", encoding='utf-8') as f:
        f.write(content)
        
    api.upload_file(path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset")
    os.remove(temp_path)
    
    db = get_sub_db()
    subs = db.get("subtitles", [])
    subs.append({
        "sub_slug": sub_slug,
        "media_slug": media_slug,
        "language": language,
        "path": repo_path,
        "uploaded_at": datetime.utcnow().isoformat() + "Z"
    })
    db["subtitles"] = subs
    save_sub_db(db)
    
    return {"status": "success", "message": f"Subtitle ({language}) linked to media."}

# Fixed parameter path capturing for slugs with slashes
@app.get("/api/subtitles/list/{media_slug:path}")
async def list_subtitles(media_slug: str, access: dict = Depends(verify_view_access)):
    db = get_sub_db()
    return [s for s in db.get("subtitles", []) if s["media_slug"] == media_slug]

@app.get("/sub/{sub_slug}")
async def serve_subtitle_file(sub_slug: str):
    db = get_sub_db()
    sub_record = next((s for s in db.get("subtitles", []) if s["sub_slug"] == sub_slug), None)
    if not sub_record: raise HTTPException(status_code=404, detail="Subtitle not found.")
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename=sub_record["path"], repo_type="dataset", token=HF_TOKEN)
        return FileResponse(path=file_path, media_type="text/vtt")
    except: raise HTTPException(status_code=500, detail="Error loading subtitle file.")

# --- Massive HTML/JS Payload (Universal Cinematic Media Tube) ---
MEDIA_TUBE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qlynk Tube - Universal Vault</title>
    <link rel="icon" type="image/png" href="//qlynk.vercel.app/quicklink-logo.png">
    <script src="https://www.youtube.com/iframe_api"></script>
    <style>
        :root {
            --yt-bg: #0f0f0f; --yt-card: #212121; --yt-hover: #3d3d3d;
            --yt-text: #f1f1f1; --yt-muted: #aaaaaa; --yt-brand: #bc8cff; --yt-border: #3f3f3f;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: "Roboto", "Arial", sans-serif; background-color: var(--yt-bg); color: var(--yt-text); overflow-x: hidden; }
        
        .navbar { display: flex; justify-content: space-between; align-items: center; padding: 10px 24px; background: var(--yt-bg); position: sticky; top: 0; z-index: 1000; border-bottom: 1px solid var(--yt-border); }
        .logo { font-size: 20px; font-weight: bold; color: #fff; text-decoration: none; display: flex; align-items: center; gap: 8px; cursor: pointer;}
        .logo span { color: var(--yt-brand); transition: color 0.3s;}
        .search-box { display: flex; align-items: center; width: 40%; max-width: 600px; background: var(--yt-bg); border: 1px solid var(--yt-border); border-radius: 40px; overflow: hidden; position: relative;}
        .search-box input { flex: 1; background: transparent; border: none; color: #fff; padding: 10px 20px; font-size: 16px; outline: none; }
        .search-box button { background: var(--yt-card); border: none; border-left: 1px solid var(--yt-border); color: var(--yt-text); padding: 10px 20px; cursor: pointer; transition: 0.2s; }
        
        .container { padding: 24px; max-width: 1600px; margin: 0 auto; }
        
        .video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; row-gap: 40px; }
        .vid-card { cursor: pointer; text-decoration: none; color: inherit; display: flex; flex-direction: column; transition: transform 0.2s;}
        .vid-card:hover { transform: scale(1.02); }
        .thumb-wrapper { position: relative; width: 100%; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; background: #000; margin-bottom: 12px; border: 1px solid var(--yt-border);}
        .thumb-img { width: 100%; height: 100%; object-fit: cover; }
        .type-badge { position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.8); padding: 3px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; border: 1px solid var(--yt-brand);}
        .vid-title { font-size: 16px; font-weight: 500; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .vid-meta { font-size: 13px; color: var(--yt-muted); }

        .watch-layout { display: flex; gap: 24px; flex-wrap: wrap; }
        .primary-col { flex: 1; min-width: 65%; max-width: 1200px; }
        .secondary-col { width: 350px; flex-shrink: 0; display: flex; flex-direction: column; gap: 15px;}
        
        /* PLAYER ARCHITECTURE */
        .player-wrapper { width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 12px; overflow: hidden; position: relative; box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center;}
        .player-element { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain; z-index: 5; display: block;}
        .yt-container { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 4; pointer-events: none;}
        
        /* Audio Visuals */
        .audio-disc { width: 250px; height: 250px; border-radius: 50%; object-fit: cover; border: 4px solid var(--yt-brand); animation: spin 8s linear infinite; z-index: 6; box-shadow: 0 0 40px rgba(0,0,0,0.8); display: block; transition: border-color 0.3s;}
        .audio-visualizer { position: absolute; bottom: 0; left: 0; width: 100%; height: 100%; z-index: 4; pointer-events: none;}
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        /* Action UI Overlay */
        .action-icon-overlay { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.7); color: #fff; padding: 20px 30px; border-radius: 50px; font-size: 32px; font-weight: bold; z-index: 80; opacity: 0; pointer-events: none; display: flex; align-items: center; gap: 15px; transition: opacity 0.2s, transform 0.2s; backdrop-filter: blur(5px);}
        .action-icon-overlay.show { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
        .fast-forward-overlay { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: #fff; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; z-index: 100; display: none; pointer-events: none; align-items: center; gap: 8px;}
        
        .custom-controls { position: absolute; bottom: 0; left: 0; width: 100%; padding: 60px 20px 10px 20px; background: linear-gradient(transparent, rgba(0,0,0,0.95)); z-index: 50; display: flex; flex-direction: column; gap: 8px; opacity: 0; transition: opacity 0.3s;}
        .player-wrapper:hover .custom-controls, .custom-controls.active { opacity: 1; }
        
        .seek-container { width: 100%; height: 5px; background: rgba(255,255,255,0.2); border-radius: 3px; cursor: pointer; position: relative; transition: height 0.1s;}
        .seek-container:hover { height: 8px; }
        .seek-progress { height: 100%; background: var(--yt-brand); border-radius: 3px; width: 0%; pointer-events: none; transition: background 0.3s;}
        
        .control-row { display: flex; justify-content: space-between; align-items: center; color: #fff;}
        .ctrl-left, .ctrl-right { display: flex; align-items: center; gap: 15px; }
        .ctrl-btn { background: none; border: none; color: #fff; font-size: 20px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s;}
        .ctrl-btn:hover { color: var(--yt-brand); }
        .ctrl-btn.active-state { color: var(--yt-brand); }
        .time-display { font-size: 13px; font-family: monospace;}
        
        .volume-slider { width: 0px; opacity: 0; transition: 0.3s; -webkit-appearance: none; background: transparent; cursor: pointer;}
        .volume-container:hover .volume-slider, .volume-slider.active { width: 80px; opacity: 1; margin-left: 5px;}
        .volume-slider::-webkit-slider-thumb { -webkit-appearance: none; height: 12px; width: 12px; border-radius: 50%; background: var(--yt-brand); margin-top: -4px;}
        .volume-slider::-webkit-slider-runnable-track { width: 100%; height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px;}

        .settings-menu { position: absolute; bottom: 60px; right: 20px; background: rgba(28,28,28,0.95); border-radius: 8px; padding: 15px; z-index: 60; display: none; flex-direction: column; min-width: 220px; border: 1px solid var(--yt-border); backdrop-filter: blur(10px); max-height: 300px; overflow-y: auto;}
        .settings-menu.show { display: flex; }
        .setting-item { display: flex; justify-content: space-between; padding: 10px; font-size: 13px; cursor: pointer; border-radius: 4px;}
        .setting-item:hover { background: rgba(255,255,255,0.1); }
        .speed-slider { -webkit-appearance: none; width: 100%; background: transparent; margin-top: 10px;}
        .speed-slider::-webkit-slider-thumb { -webkit-appearance: none; height: 14px; width: 14px; border-radius: 50%; background: var(--yt-brand); margin-top: -5px;}
        .speed-slider::-webkit-slider-runnable-track { width: 100%; height: 4px; background: rgba(255,255,255,0.3); border-radius: 2px;}

        .custom-context { position: absolute; background: #212121; border: 1px solid var(--yt-border); border-radius: 4px; padding: 5px 0; z-index: 1000; display: none; box-shadow: 0 4px 10px rgba(0,0,0,0.5);}
        .context-item { padding: 8px 20px; font-size: 13px; cursor: pointer; color: #fff;}
        .context-item:hover { background: var(--yt-hover); }

        .watch-title { font-size: 20px; font-weight: bold; margin: 15px 0 5px 0; word-break: break-all;}
        .video-visualizer { width: 100%; height: 40px; margin-bottom: 10px; border-radius: 4px; display: none; pointer-events: none;}
        .watch-actions { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--yt-border); padding-bottom: 15px; margin-bottom: 15px; flex-wrap: wrap; gap: 10px;}
        .channel-info { display: flex; align-items: center; gap: 12px; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; background: var(--yt-brand); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 18px; color: #000; transition: background 0.3s;}
        
        .action-btns { display: flex; gap: 10px; flex-wrap: wrap;}
        .btn { display: flex; align-items: center; gap: 8px; background: var(--yt-card); color: #fff; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-weight: 500; font-size: 14px; transition: 0.2s;}
        .btn:hover { background: var(--yt-hover); }
        .btn-primary { background: var(--yt-text); color: #000; text-decoration: none;}
        .btn-share { background: var(--yt-brand); color: #000; font-weight: bold; border-radius: 4px; }
        
        .description-box { background: var(--yt-card); padding: 15px; border-radius: 12px; font-size: 14px; line-height: 1.5; color: #e1e1e1;}
        
        .related-card { display: flex; gap: 10px; cursor: pointer; text-decoration: none; color: inherit; padding: 5px; border-radius: 8px; transition: background 0.2s;}
        .related-card:hover { background: rgba(255,255,255,0.05); }
        .related-card .thumb-wrapper { width: 140px; border-radius: 8px; margin-bottom: 0; flex-shrink: 0;}
        .related-info { display: flex; flex-direction: column; }
        .related-title { font-size: 14px; font-weight: 500; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; overflow: hidden; }
        .yt-pill { font-size: 12px; background: #ff0000; color: #fff; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px; width: max-content;}

        .modal-overlay { position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.8); z-index: 2000; justify-content:center; align-items:center; display:none;}
        .modal-box { background: var(--yt-card); width: 400px; padding: 25px; border-radius: 12px; border: 1px solid var(--yt-border); display:flex; flex-direction:column; gap:15px;}
        .drop-zone { border: 2px dashed var(--yt-border); padding: 30px; text-align: center; border-radius: 8px; cursor: pointer; color: var(--yt-muted); transition: 0.2s;}
        .drop-zone:hover { border-color: var(--yt-brand); color: #fff;}
        .modal-input { width: 100%; padding: 10px; background: #000; border: 1px solid var(--yt-border); color: #fff; border-radius: 6px; outline:none;}
        
        .hidden { display: none !important; }
        .theater-mode .primary-col { min-width: 100%; max-width: 100%; }
        .theater-mode .secondary-col { width: 100%; margin-top: 20px;}
        ::cue { background-color: rgba(0,0,0,0.8); color: white; font-family: sans-serif; font-size: 100%; }

        @media(max-width: 1000px) { .primary-col { min-width: 100%; } .secondary-col { width: 100%; } .search-box { width: 60%; } }
        @media(max-width: 600px) { .search-box { display: none; } .custom-controls { padding: 40px 10px 10px 10px;} .ctrl-btn { font-size: 16px;} .volume-slider{ display:none; } }
    </style>
</head>
<body>

    <div class="navbar">
        <div class="logo" onclick="goHome()">▶ <span id="brandLogo">Qlynk</span>Vault</div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search secure vault or paste YouTube URL..." onkeyup="if(event.key === 'Enter') handleSearch()">
            <button onclick="handleSearch()">🔍</button>
        </div>
        <div style="display: flex; gap: 15px; align-items: center;">
            <button onclick="generateShareLink()" class="btn btn-share" id="shareBtn" style="display:none;">🔗 Share</button>
            <div class="avatar" id="navAvatar" style="width: 32px; height: 32px; font-size:14px; cursor:pointer;" onclick="window.location.href='/'">Q</div>
        </div>
    </div>

    <div class="container">
        <h2 id="loadingText" style="text-align:center; color: var(--yt-muted); margin-top:50px;">Verifying Secure Token...</h2>

        <div id="homeView" class="video-grid hidden"></div>

        <div id="watchView" class="watch-layout hidden">
            <div class="primary-col">
                <div class="player-wrapper" id="playerWrapper" oncontextmenu="return false;">
                </div>
                
                <h1 class="watch-title" id="wTitle">Loading...</h1>
                <canvas id="videoVisualizer" class="video-visualizer"></canvas>
                
                <div class="watch-actions" style="margin-top:15px;">
                    <div class="channel-info">
                        <div class="avatar" id="wAvatar">Q</div>
                        <div>
                            <div style="font-weight: bold; font-size: 16px;" id="wType">Engine</div>
                            <div style="font-size: 12px; color: var(--yt-muted);" id="wSize">0 MB</div>
                        </div>
                    </div>
                    <div class="action-btns">
                        <button class="btn" onclick="openSubModal()" id="addSubBtn" style="display:none;">➕ Add CC</button>
                        <button class="btn" onclick="toggleTheater()">📺 Theater</button>
                        <button class="btn" onclick="togglePiP()" id="pipBtn">🔲 PiP</button>
                        <a href="#" class="btn btn-primary" id="wDownload" download>⬇ Download</a>
                    </div>
                </div>

                <div class="description-box">
                    <span id="wDate" style="display:block; margin-bottom:8px; color:var(--yt-muted);">Uploaded on: Unknown</span>
                    <div id="subsList" style="margin-bottom: 10px; color: var(--accent-green); font-size:12px;"></div>
                    <p>Protected by Qlynk Universal Engine. Native & Hybrid YouTube parsing active. Advanced UI, Repeat, Shuffle, and Spacebar Logic supported.</p>
                </div>
            </div>

            <div class="secondary-col">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <h3>Up Next</h3>
                    <label style="font-size:12px; display:flex; align-items:center; gap:5px; cursor:pointer;">
                        <input type="checkbox" id="autoplayToggle" checked> Autoplay
                    </label>
                </div>
                <div id="relatedVideos"></div>
            </div>
        </div>
    </div>

    <div class="custom-context" id="customContext">
        <div class="context-item" onclick="copyVidUrl()">📋 Copy video URL</div>
    </div>

    <div class="modal-overlay" id="subModal">
        <div class="modal-box">
            <h3>Upload Subtitle (SRT / VTT)</h3>
            <div class="drop-zone" id="dropZone" onclick="document.getElementById('subFile').click()">
                Drop Subtitle File Here<br>or Click to Browse
            </div>
            <input type="file" id="subFile" style="display:none" accept=".srt,.vtt" onchange="fileSelected(this)">
            <p id="selectedFileName" style="font-size:12px; color:var(--yt-brand); text-align:center;"></p>
            <input type="text" id="subLang" class="modal-input" placeholder="Language (Auto-Detected or Type)">
            <div style="display:flex; gap:10px; margin-top:10px;">
                <button class="btn" style="flex:1;" onclick="closeSubModal()">Cancel</button>
                <button class="btn btn-primary" style="flex:1; background:var(--yt-brand);" onclick="submitSubtitle()">Upload & Link</button>
            </div>
        </div>
    </div>

    <script>
        // --- AUTH & INITIALIZATION ---
        const urlParams = new URLSearchParams(window.location.search);
        const tokenFromUrl = urlParams.get('token');
        if (tokenFromUrl) {
            document.cookie = "share_token=" + tokenFromUrl + "; path=/; max-age=86400";
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        const isAdmin = document.cookie.includes('auth_token=');

        const FALLBACK_THUMB = "https://qlynk.vercel.app/Quicklink-Banner.png";
        const SVG_MUSIC = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23bc8cff"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>`;
        
        let masterLibrary = [];
        let currentAudioCtx = null;
        let currentAnimationId = null;
        let activeSlug = null;
        let ytIdActive = null;
        
        // Universal Player State
        let activePlayer = null; 
        let ytPlayer = null;
        let controlTimeout;
        let clickTimer = null;
        let isSpaceHolding = false;
        let spacePressTime = 0;
        let normalSpeed = 1.0;
        let isRepeat = false;
        let isShuffle = false;
        let ytPollInterval = null;

        function formatBytes(bytes) {
            if(bytes === 0) return '0 B';
            const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        function formatTime(sec) {
            if(isNaN(sec)) return '0:00';
            let m = Math.floor(sec / 60); let s = Math.floor(sec % 60);
            return m + ':' + (s < 10 ? '0' : '') + s;
        }
        function getMediaType(m) {
            if(!m) return 'file'; if(m.startsWith('video/')) return 'video';
            if(m.startsWith('audio/')) return 'audio'; if(m.startsWith('image/')) return 'image';
            return 'file';
        }
        
        // Robust YT Regex
        function extractYtId(url) {
            const p = /^(?:https?:\/\/)?(?:m\.|www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))((\w|-){11})(?:\S+)?$/;
            return (url.match(p)) ? RegExp.$1 : null;
        }

        // Dominant Color Engine with CORS fallback
        function applyDominantColor(imgSrc, fallback = '#bc8cff') {
            const img = new Image();
            img.crossOrigin = "Anonymous";
            img.src = imgSrc;
            img.onload = () => {
                const c = document.createElement('canvas'); const ctx = c.getContext('2d');
                c.width = img.width || 100; c.height = img.height || 100;
                ctx.drawImage(img, 0, 0, c.width, c.height);
                try {
                    const data = ctx.getImageData(0,0,c.width,c.height).data;
                    let r=0,g=0,b=0, count=0;
                    for(let i=0; i<data.length; i+=16) { r+=data[i]; g+=data[i+1]; b+=data[i+2]; count++; }
                    const hex = `rgb(${~~(r/count)},${~~(g/count)},${~~(b/count)})`;
                    setThemeColor(hex);
                } catch(e) { setThemeColor(fallback); } // CORS fallback
            };
            img.onerror = () => setThemeColor(fallback);
        }

        function setThemeColor(color) {
            document.documentElement.style.setProperty('--yt-brand', color);
            window.currentThemeColor = color;
        }

        async function init() {
            try {
                const res = await fetch('/api/media_library');
                if(res.status === 401) return document.getElementById('loadingText').innerHTML = "🔒 <b>ACCESS DENIED</b>";
                
                if(isAdmin) {
                    document.getElementById('shareBtn').style.display = 'block';
                    document.getElementById('addSubBtn').style.display = 'flex';
                } else {
                    document.getElementById('wDownload').style.display = 'none';
                    document.getElementById('addSubBtn').style.display = 'none';
                }
                
                masterLibrary = await res.json();
                document.getElementById('loadingText').classList.add('hidden');
                routeHandler();
            } catch(e) { document.getElementById('loadingText').innerText = "Connection Error."; }
        }

        function routeHandler() {
            const path = window.location.pathname;
            const params = new URLSearchParams(window.location.search);
            
            // Clean up player state
            if(currentAudioCtx) { currentAudioCtx.close(); currentAudioCtx = null; }
            if(currentAnimationId) cancelAnimationFrame(currentAnimationId);
            if(ytPollInterval) clearInterval(ytPollInterval);
            if(ytPlayer && ytPlayer.destroy) ytPlayer.destroy();
            setThemeColor('#bc8cff');

            if(path === '/video' || path === '/video/') {
                activeSlug = params.get('q');
                ytIdActive = params.get('yt');
                if (ytIdActive) renderYtPage(ytIdActive);
                else if (activeSlug) renderWatchPage(activeSlug); 
                else goHome();
            } else {
                renderHomeGrid(params.get('search'));
            }
        }

        function goHome() { window.history.pushState({}, '', '/view'); routeHandler(); }
        
        function handleSearch() {
            const q = document.getElementById('searchInput').value.trim();
            const ytMatch = extractYtId(q);
            if(ytMatch) {
                window.history.pushState({}, '', `/video?yt=${ytMatch}`); routeHandler();
            } else {
                window.history.pushState({}, '', `/view?search=${encodeURIComponent(q)}`); routeHandler();
            }
        }

        function renderHomeGrid(searchQuery = null) {
            document.getElementById('watchView').classList.add('hidden');
            const grid = document.getElementById('homeView');
            grid.classList.remove('hidden'); grid.innerHTML = '';

            let data = masterLibrary;
            if(searchQuery) {
                const q = searchQuery.toLowerCase();
                data = masterLibrary.filter(f => f.title.toLowerCase().includes(q) || f.slug.toLowerCase().includes(q));
            }
            data.forEach(f => {
                const type = getMediaType(f.mime_type);
                const card = document.createElement('a');
                card.href = `/video?q=${f.slug}`; card.className = 'vid-card';
                card.onclick = (e) => { e.preventDefault(); window.history.pushState({}, '', `/video?q=${f.slug}`); routeHandler(); };
                card.innerHTML = `<div class="thumb-wrapper"><img src="${f.thumbnail || FALLBACK_THUMB}" class="thumb-img" onerror="this.src='${FALLBACK_THUMB}'"><div class="type-badge">${type}</div></div><div class="vid-title">${f.title}</div><div class="vid-meta">Vault • ${formatBytes(f.size_bytes)}</div>`;
                grid.appendChild(card);
            });
        }

        // --- MEDIA SESSION API (Bluetooth & Keyboard keys) ---
        function setupMediaSession(title, artist, artworkSrc) {
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: title, artist: artist, album: 'Qlynk Universal',
                    artwork: [ { src: artworkSrc || FALLBACK_THUMB, sizes: '512x512', type: 'image/png' } ]
                });

                navigator.mediaSession.setActionHandler('play', () => { if(activePlayer) activePlayer.play(); });
                navigator.mediaSession.setActionHandler('pause', () => { if(activePlayer) activePlayer.pause(); });
                navigator.mediaSession.setActionHandler('seekbackward', (d) => { if(activePlayer) activePlayer.seek(Math.max(activePlayer.currentTime() - (d.seekOffset || 5), 0)); });
                navigator.mediaSession.setActionHandler('seekforward', (d) => { if(activePlayer) activePlayer.seek(Math.min(activePlayer.currentTime() + (d.seekOffset || 5), activePlayer.duration())); });
                navigator.mediaSession.setActionHandler('nexttrack', () => { window.nextVid(); });
                navigator.mediaSession.setActionHandler('previoustrack', () => { if(activePlayer) activePlayer.seek(0); });
            }
        }

        window.showActionIcon = function(text) {
            const icon = document.getElementById('actionIcon');
            if(!icon) return;
            icon.innerText = text;
            icon.classList.add('show');
            clearTimeout(window.iconTimeout);
            window.iconTimeout = setTimeout(() => icon.classList.remove('show'), 600);
        }

        function getControlsHtml() {
            return `
                <div class="action-icon-overlay" id="actionIcon"></div>
                <div class="fast-forward-overlay" id="ffOverlay">Fast Forwarding 2x ▶▶</div>
                <div class="custom-controls" id="pControls">
                    <div class="seek-container" id="pSeek"><div class="seek-progress" id="pSeekProg"></div></div>
                    <div class="control-row">
                        <div class="ctrl-left">
                            <button class="ctrl-btn" id="pPlay">▶</button>
                            <button class="ctrl-btn" id="pNext" onclick="nextVid()">⏭</button>
                            <div class="volume-container" style="display:flex; align-items:center;">
                                <button class="ctrl-btn" id="pMute">🔊</button>
                                <input type="range" class="volume-slider" id="pVol" min="0" max="1" step="0.05" value="1">
                            </div>
                            <span class="time-display" id="pTime">0:00 / 0:00</span>
                        </div>
                        <div class="ctrl-right">
                            <button class="ctrl-btn" id="pShuffle" onclick="toggleShuffle()" title="Shuffle">🔀</button>
                            <button class="ctrl-btn" id="pRepeat" onclick="toggleRepeat()" title="Repeat">🔁</button>
                            <button class="ctrl-btn" id="pCC" title="Subtitles">💬</button>
                            <button class="ctrl-btn" id="pSetBtn" title="Settings">⚙️</button>
                            <button class="ctrl-btn" id="pFull">⛶</button>
                        </div>
                    </div>
                </div>
                <div class="settings-menu" id="pSettings">
                    <div style="font-weight:bold; margin-bottom:5px; color:var(--yt-brand);">Playback Speed</div>
                    <div style="display:flex; gap:5px; margin-bottom:10px;">
                        <button class="btn" style="padding:4px 8px; font-size:11px;" onclick="setSpeed(1)">1x</button>
                        <button class="btn" style="padding:4px 8px; font-size:11px;" onclick="setSpeed(2)">2x</button>
                    </div>
                    <input type="range" class="speed-slider" id="pSpeedRange" min="0.25" max="4" step="0.25" value="1">
                    <div style="text-align:center; font-size:11px; margin-bottom:10px;" id="speedDisplay">1.00x</div>
                    <div id="ytQualitySection" style="display:none;">
                        <div style="font-weight:bold; margin-bottom:5px; color:var(--yt-brand);">Quality</div>
                        <div id="pYtQualityList" style="display:flex; flex-wrap:wrap; gap:5px; margin-bottom:10px;"></div>
                    </div>
                    <div style="font-weight:bold; margin-bottom:5px; color:var(--yt-brand);">Subtitles</div>
                    <div id="pCcList"></div>
                </div>
            `;
        }

        // --- RENDER LOCAL WATCH PAGE ---
        async function renderWatchPage(slug) {
            document.getElementById('homeView').classList.add('hidden');
            document.getElementById('watchView').classList.remove('hidden');
            
            const file = masterLibrary.find(f => f.slug === slug);
            if(!file) return document.getElementById('wTitle').innerText = "File Not Found.";

            document.getElementById('wTitle').innerText = file.title;
            document.getElementById('wSize').innerText = formatBytes(file.size_bytes);
            document.getElementById('wType').innerText = getMediaType(file.mime_type).toUpperCase();
            document.getElementById('wDate').innerText = `Uploaded on: ${new Date(file.uploaded_at).toLocaleDateString()}`;
            document.getElementById('wDownload').style.display = isAdmin ? 'flex' : 'none';
            document.getElementById('wDownload').href = file.is_external ? file.external_url : `/f/${file.slug}`;

            const pw = document.getElementById('playerWrapper');
            const type = getMediaType(file.mime_type);
            pw.innerHTML = ''; document.getElementById('videoVisualizer').style.display = 'none';

            let subs = [];
            try { const r = await fetch(`/api/subtitles/list/${encodeURIComponent(slug)}`); if(r.ok) subs = await r.json(); } catch(e){}
            let trackHtml = subs.map((s,i) => `<track kind="subtitles" src="/sub/${s.sub_slug}" srclang="${s.language.substring(0,2).toLowerCase()}" label="${s.language}" ${i===0?'default':''}>`).join('');

            applyDominantColor(file.thumbnail || FALLBACK_THUMB);

            if(type === 'video') {
                pw.innerHTML = `<video id="mainMedia" class="player-element" src="${file.is_external ? file.external_url : `/f/${file.slug}`}" crossorigin="anonymous" playsinline>${trackHtml}</video>` + getControlsHtml();
                document.getElementById('videoVisualizer').style.display = 'block';
                setTimeout(() => initVisualizer('mainMedia', 'videoVisualizer', 'bar', window.currentThemeColor), 500);
            } 
            else if(type === 'audio') {
                const thumb = file.thumbnail || SVG_MUSIC;
                pw.innerHTML = `
                    <img id="audioDisc" src="${thumb}" class="audio-disc" onerror="this.src='${SVG_MUSIC}'">
                    <canvas id="audioVisualizer" class="audio-visualizer"></canvas>
                    <audio id="mainMedia" src="${file.is_external ? file.external_url : `/f/${file.slug}`}" crossorigin="anonymous" style="display:none;">${trackHtml}</audio>
                ` + getControlsHtml();
                setTimeout(() => initVisualizer('mainMedia', 'audioVisualizer', 'wave', window.currentThemeColor), 500);
            } 
            
            setupMediaSession(file.title, 'Qlynk Vault', file.thumbnail);
            
            const ccList = document.getElementById('pCcList');
            if(ccList) {
                ccList.innerHTML = `<div class="setting-item" onclick="setCC(-1)">Off</div>` + subs.map((s,i) => `<div class="setting-item" onclick="setCC(${i})">${s.language}</div>`).join('');
            }
            if(subs.length > 0) document.getElementById('subsList').innerText = `CC Available: ${subs.map(s=>s.language).join(', ')}`;
            else document.getElementById('subsList').innerText = `No Subtitles (CC) linked.`;
            
            const mediaEl = document.getElementById('mainMedia');
            if(mediaEl) {
                // Map HTML5 Media to Universal Interface
                activePlayer = {
                    play: () => mediaEl.play(),
                    pause: () => mediaEl.pause(),
                    seek: (t) => mediaEl.currentTime = t,
                    setVolume: (v) => { mediaEl.volume = v; mediaEl.muted = false; },
                    toggleMute: () => mediaEl.muted = !mediaEl.muted,
                    currentTime: () => mediaEl.currentTime,
                    duration: () => mediaEl.duration || 0,
                    setSpeed: (s) => mediaEl.playbackRate = s,
                    isPaused: () => mediaEl.paused,
                    isMuted: () => mediaEl.muted,
                    getVolume: () => mediaEl.volume
                };

                mediaEl.play().catch(e => console.log("Autoplay blocked."));
                mediaEl.addEventListener('ended', handleMediaEnded);
                mediaEl.ontimeupdate = updateProgressUI;
                mediaEl.onplay = () => document.getElementById('pPlay').innerText = '⏸';
                mediaEl.onpause = () => document.getElementById('pPlay').innerText = '▶';
            }
            initCustomControls();
            renderHybridRelated(file.title);
        }

        // --- RENDER YOUTUBE HYBRID PAGE ---
        function renderYtPage(ytId) {
            document.getElementById('homeView').classList.add('hidden');
            document.getElementById('watchView').classList.remove('hidden');
            
            document.getElementById('wTitle').innerText = "YouTube Stream Loading...";
            document.getElementById('wType').innerText = "YOUTUBE";
            document.getElementById('wSize').innerText = "STREAM";
            document.getElementById('wDownload').style.display = 'none';
            document.getElementById('addSubBtn').style.display = 'none';
            document.getElementById('subsList').innerText = "Using native YT Captions";

            const thumb = `https://img.youtube.com/vi/${ytId}/maxresdefault.jpg`;
            applyDominantColor(thumb, '#ff0000'); // Default YT Red fallback

            const pw = document.getElementById('playerWrapper');
            pw.innerHTML = `<div id="ytContainer" class="yt-container"><div id="ytPlayerDiv"></div></div>` + getControlsHtml();
            document.getElementById('videoVisualizer').style.display = 'block';

            // Init YT Player
            ytPlayer = new YT.Player('ytPlayerDiv', {
                videoId: ytId,
                playerVars: { 'autoplay': 1, 'controls': 0, 'disablekb': 1, 'fs': 0, 'rel': 0, 'modestbranding': 1 },
                events: {
                    'onReady': onYtReady,
                    'onStateChange': onYtStateChange
                }
            });
            renderHybridRelated("YouTube Query"); // Fallback text until API loads title
        }

        function onYtReady(event) {
            document.getElementById('wTitle').innerText = ytPlayer.getVideoData().title;
            setupMediaSession(ytPlayer.getVideoData().title, 'YouTube Stream', `https://img.youtube.com/vi/${ytIdActive}/maxresdefault.jpg`);
            
            // Map YT to Universal Interface
            activePlayer = {
                play: () => ytPlayer.playVideo(),
                pause: () => ytPlayer.pauseVideo(),
                seek: (t) => ytPlayer.seekTo(t, true),
                setVolume: (v) => { ytPlayer.setVolume(v * 100); ytPlayer.unMute(); },
                toggleMute: () => ytPlayer.isMuted() ? ytPlayer.unMute() : ytPlayer.mute(),
                currentTime: () => ytPlayer.getCurrentTime(),
                duration: () => ytPlayer.getDuration() || 0,
                setSpeed: (s) => ytPlayer.setPlaybackRate(s),
                isPaused: () => ytPlayer.getPlayerState() !== YT.PlayerState.PLAYING,
                isMuted: () => ytPlayer.isMuted(),
                getVolume: () => ytPlayer.getVolume() / 100
            };

            initCustomControls();
            
            // Sync Quality Levels
            const qList = ytPlayer.getAvailableQualityLevels();
            if(qList && qList.length > 0) {
                document.getElementById('ytQualitySection').style.display = 'block';
                document.getElementById('pYtQualityList').innerHTML = qList.map(q => `<button class="btn" style="padding:4px 8px; font-size:11px;" onclick="ytPlayer.setPlaybackQuality('${q}')">${q}</button>`).join('');
            }

            // Sync YT Captions to menu
            const ccMod = ytPlayer.getOptions('captions') || ytPlayer.getOptions('cc');
            const ccList = document.getElementById('pCcList');
            if(ccList) {
                ccList.innerHTML = `<div class="setting-item" onclick="ytPlayer.unloadModule('captions')">Off</div>
                                    <div class="setting-item" onclick="ytPlayer.loadModule('captions')">Auto Enable YT CC</div>`;
            }

            ytPollInterval = setInterval(updateProgressUI, 500);
            simulateYtVisualizer();
        }

        function onYtStateChange(event) {
            const pPlay = document.getElementById('pPlay');
            if (event.data == YT.PlayerState.PLAYING) pPlay.innerText = '⏸';
            else if (event.data == YT.PlayerState.PAUSED) pPlay.innerText = '▶';
            else if (event.data == YT.PlayerState.ENDED) handleMediaEnded();
        }

        function simulateYtVisualizer() {
            const canvas = document.getElementById('videoVisualizer');
            if(!canvas) return;
            const ctx = canvas.getContext('2d');
            const numBars = 32;
            
            function drawYt() {
                if(!ytIdActive) return;
                currentAnimationId = requestAnimationFrame(drawYt);
                if(ytPlayer && ytPlayer.getPlayerState() !== YT.PlayerState.PLAYING) return; // Only bounce if playing

                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = canvas.clientHeight || 40;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const barWidth = (canvas.width / numBars) * 0.8;
                const centerY = canvas.height / 2;
                let x = (canvas.width - (barWidth + 2) * numBars) / 2;
                
                for(let i = 0; i < numBars; i++) {
                    const randomVal = Math.random();
                    const barHeight = randomVal * (canvas.height / 2.2);
                    ctx.fillStyle = window.currentThemeColor || '#bc8cff';
                    ctx.fillRect(x, centerY - barHeight, barWidth, barHeight); 
                    ctx.fillRect(x, centerY, barWidth, barHeight); 
                    x += barWidth + 2;
                }
            }
            drawYt();
        }

        // --- UNIVERSAL CONTROL LOGIC ---
        function updateProgressUI() {
            if(!activePlayer) return;
            const cur = activePlayer.currentTime();
            const dur = activePlayer.duration();
            const percent = dur > 0 ? (cur / dur) * 100 : 0;
            document.getElementById('pSeekProg').style.width = `${percent}%`;
            document.getElementById('pTime').innerText = `${formatTime(cur)} / ${formatTime(dur)}`;
        }

        function initCustomControls() {
            const pPlay = document.getElementById('pPlay');
            const pSeek = document.getElementById('pSeek');
            const pVol = document.getElementById('pVol');
            const pMute = document.getElementById('pMute');
            const pw = document.getElementById('playerWrapper');
            const pControls = document.getElementById('pControls');
            
            pPlay.onclick = () => activePlayer.isPaused() ? activePlayer.play() : activePlayer.pause();
            
            pSeek.onclick = (e) => {
                const rect = pSeek.getBoundingClientRect();
                activePlayer.seek(((e.clientX - rect.left) / rect.width) * activePlayer.duration());
            };

            pVol.oninput = (e) => { 
                activePlayer.setVolume(e.target.value); 
                pMute.innerText = e.target.value > 0 ? '🔊' : '🔇'; 
            };
            
            pMute.onclick = () => { 
                activePlayer.toggleMute(); 
                pMute.innerText = activePlayer.isMuted() ? '🔇' : '🔊'; 
                pVol.value = activePlayer.isMuted() ? 0 : activePlayer.getVolume();
            };
            
            document.getElementById('pFull').onclick = () => { document.fullscreenElement ? document.exitFullscreen() : pw.requestFullscreen(); };
            document.getElementById('pSetBtn').onclick = (e) => { e.stopPropagation(); document.getElementById('pSettings').classList.toggle('show'); };
            document.getElementById('pSpeedRange').oninput = (e) => { setSpeed(e.target.value); };

            pw.onmousemove = () => {
                pControls.classList.add('active');
                clearTimeout(controlTimeout);
                controlTimeout = setTimeout(() => pControls.classList.remove('active'), 3000);
            };

            // Smart Center Click
            pw.onclick = (e) => {
                if(e.target.closest('.custom-controls') || e.target.closest('.settings-menu')) return;
                if(e.detail === 1) { 
                    clickTimer = setTimeout(() => {
                        activePlayer.isPaused() ? activePlayer.play() : activePlayer.pause();
                        showActionIcon(activePlayer.isPaused() ? '⏸ Pause' : '▶ Play');
                    }, 200); 
                }
            };

            pw.ondblclick = (e) => {
                e.preventDefault();
                clearTimeout(clickTimer); 
                if(e.target.closest('.custom-controls')) return;
                
                if(window.innerWidth <= 768) {
                    const rect = pw.getBoundingClientRect();
                    if(e.clientX > rect.left + rect.width/2) { activePlayer.seek(activePlayer.currentTime() + 10); showActionIcon('⏩ 10s'); }
                    else { activePlayer.seek(activePlayer.currentTime() - 10); showActionIcon('⏪ 10s'); }
                } else {
                    document.fullscreenElement ? document.exitFullscreen() : pw.requestFullscreen();
                }
            };
        }

        window.setSpeed = function(val) {
            normalSpeed = parseFloat(val);
            if(activePlayer) activePlayer.setSpeed(normalSpeed);
            document.getElementById('pSpeedRange').value = normalSpeed;
            document.getElementById('speedDisplay').innerText = normalSpeed.toFixed(2) + 'x';
        }

        window.toggleRepeat = function() {
            isRepeat = !isRepeat;
            document.getElementById('pRepeat').classList.toggle('active-state', isRepeat);
            showActionIcon(isRepeat ? '🔁 Repeat On' : '🔁 Repeat Off');
        }
        window.toggleShuffle = function() {
            isShuffle = !isShuffle;
            document.getElementById('pShuffle').classList.toggle('active-state', isShuffle);
            showActionIcon(isShuffle ? '🔀 Shuffle On' : '🔀 Shuffle Off');
        }

        function handleMediaEnded() {
            if (isRepeat && activePlayer) { activePlayer.seek(0); activePlayer.play(); }
            else if (isShuffle) { 
                const cards = document.querySelectorAll('.related-card');
                if(cards.length > 0) cards[Math.floor(Math.random() * cards.length)].click();
            }
            else if (document.getElementById('autoplayToggle').checked) nextVid();
        }

        window.nextVid = function() {
            const nextItem = document.querySelector('.related-card');
            if(nextItem) nextItem.click();
        }

        // --- SPACEBAR PRO & KEYBOARD HUB ---
        document.addEventListener('keydown', (e) => {
            if(document.activeElement.tagName === 'INPUT' || !activePlayer) return;

            switch(e.code) {
                case 'Space': 
                    e.preventDefault();
                    if(!e.repeat && spacePressTime === 0) spacePressTime = Date.now();
                    if(spacePressTime > 0 && (Date.now() - spacePressTime > 250) && !isSpaceHolding) {
                        isSpaceHolding = true;
                        activePlayer.setSpeed(2.0);
                        document.getElementById('ffOverlay').style.display = 'flex';
                    }
                    break;
                case 'ArrowRight':
                    e.preventDefault(); activePlayer.seek(activePlayer.currentTime() + 5); showActionIcon('⏩ 5s'); break;
                case 'ArrowLeft':
                    e.preventDefault(); activePlayer.seek(activePlayer.currentTime() - 5); showActionIcon('⏪ 5s'); break;
                case 'ArrowUp':
                    e.preventDefault(); 
                    let vU = Math.min(1, activePlayer.getVolume() + 0.05);
                    activePlayer.setVolume(vU);
                    document.getElementById('pVol').value = vU;
                    showActionIcon(`🔊 ${Math.round(vU * 100)}%`);
                    break;
                case 'ArrowDown':
                    e.preventDefault(); 
                    let vD = Math.max(0, activePlayer.getVolume() - 0.05);
                    activePlayer.setVolume(vD);
                    document.getElementById('pVol').value = vD;
                    showActionIcon(vD === 0 ? '🔇 Muted' : `🔉 ${Math.round(vD * 100)}%`);
                    break;
                case 'KeyF': 
                    e.preventDefault(); 
                    const pw = document.getElementById('playerWrapper');
                    document.fullscreenElement ? document.exitFullscreen() : pw.requestFullscreen(); 
                    break;
                case 'KeyT': e.preventDefault(); toggleTheater(); break;
                case 'KeyI': e.preventDefault(); togglePiP(); break;
                case 'KeyM': 
                    e.preventDefault(); 
                    activePlayer.toggleMute();
                    showActionIcon(activePlayer.isMuted() ? '🔇 Muted' : '🔊 Unmuted');
                    break;
            }
        });

        document.addEventListener('keyup', (e) => {
            if(document.activeElement.tagName === 'INPUT' || !activePlayer) return;

            if(e.code === 'Space') {
                e.preventDefault();
                if(isSpaceHolding) {
                    isSpaceHolding = false;
                    activePlayer.setSpeed(normalSpeed);
                    document.getElementById('ffOverlay').style.display = 'none';
                } else {
                    if (Date.now() - spacePressTime < 250) {
                        activePlayer.isPaused() ? activePlayer.play() : activePlayer.pause();
                        showActionIcon(activePlayer.isPaused() ? '⏸ Pause' : '▶ Play');
                    }
                }
                spacePressTime = 0; 
            }
        });

        document.addEventListener('contextmenu', (e) => {
            const pw = document.getElementById('playerWrapper');
            if(pw && pw.contains(e.target)) {
                e.preventDefault();
                const cm = document.getElementById('customContext');
                cm.style.display = 'block';
                cm.style.left = `${e.pageX}px`; cm.style.top = `${e.pageY}px`;
            }
        });
        document.addEventListener('click', (e) => {
            document.getElementById('customContext').style.display = 'none';
            const setMenu = document.getElementById('pSettings');
            if(setMenu && setMenu.classList.contains('show') && !setMenu.contains(e.target) && e.target.id !== 'pSetBtn') {
                setMenu.classList.remove('show');
            }
        });
        window.copyVidUrl = function() { navigator.clipboard.writeText(window.location.href); alert("Video Link Copied!"); }

        function initVisualizer(mediaId, canvasId, mode, dominantColor) {
            const media = document.getElementById(mediaId);
            const canvas = document.getElementById(canvasId);
            if(!media || !canvas) return;
            const ctx = canvas.getContext('2d');

            media.addEventListener('play', () => {
                if(currentAudioCtx) return;
                try {
                    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    currentAudioCtx = audioCtx;
                    media.crossOrigin = "anonymous";
                    const analyser = audioCtx.createAnalyser();
                    analyser.fftSize = 64; // Yields 32 bins exactly for mirrored visualizer
                    const source = audioCtx.createMediaElementSource(media);
                    source.connect(analyser); analyser.connect(audioCtx.destination);
                    const bufferLength = analyser.frequencyBinCount;
                    const dataArray = new Uint8Array(bufferLength);
                    
                    function draw() {
                        currentAnimationId = requestAnimationFrame(draw);
                        canvas.width = canvas.parentElement.clientWidth;
                        canvas.height = canvas.clientHeight || canvas.parentElement.clientHeight;
                        analyser.getByteFrequencyData(dataArray);
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        
                        const barWidth = (canvas.width / bufferLength) * 0.8;
                        const centerY = canvas.height / 2;
                        let x = (canvas.width - (barWidth + 2) * bufferLength) / 2;
                        
                        for(let i = 0; i < bufferLength; i++) {
                            const barHeight = (dataArray[i] / 255) * (canvas.height / 2.2);
                            ctx.fillStyle = window.currentThemeColor || dominantColor || '#bc8cff';
                            // Mirrored (Up and Down from Center)
                            ctx.fillRect(x, centerY - barHeight, barWidth, barHeight); 
                            ctx.fillRect(x, centerY, barWidth, barHeight); 
                            x += barWidth + 2;
                        }
                    }
                    draw();
                } catch(e) { console.warn("Visualizer CORS Blocked:", e); }
            }, {once: true});
        }

        // Subtitle Modal Functions...
        function openSubModal() { document.getElementById('subModal').style.display = 'flex'; }
        function closeSubModal() { document.getElementById('subModal').style.display = 'none'; pendingSubFile = null; document.getElementById('selectedFileName').innerText = ''; }
        function fileSelected(input) {
            if(input.files.length > 0) {
                pendingSubFile = input.files[0];
                document.getElementById('selectedFileName').innerText = `Selected: ${pendingSubFile.name}`;
            }
        }
        async function submitSubtitle() { /* Same logic as before */ }
        window.setCC = function(index) {
            const media = document.getElementById('mainMedia');
            if(!media) return;
            for(let i=0; i<media.textTracks.length; i++) {
                media.textTracks[i].mode = (i === index) ? 'showing' : 'hidden';
            }
            document.getElementById('pSettings').classList.remove('show');
        }

        // Hybrid Recommendations Engine
        function renderHybridRelated(queryText) {
            const container = document.getElementById('relatedVideos');
            container.innerHTML = '';
            
            // 1. Local Database Matches
            const currentWords = queryText.toLowerCase().split(/[\s_\-\.]+/).filter(w => w.length > 2);
            let scoredList = masterLibrary.map(f => {
                if(f.slug === activeSlug) return {file: f, score: -1};
                let score = 0;
                f.title.toLowerCase().split(/[\s_\-\.]+/).forEach(w => { if(currentWords.includes(w)) score++; });
                return {file: f, score: score};
            });
            scoredList.sort((a,b) => b.score - a.score || new Date(b.file.uploaded_at) - new Date(a.file.uploaded_at));
            
            scoredList.slice(0, 8).forEach(item => {
                if(item.score === -1) return;
                const f = item.file;
                const card = document.createElement('a');
                card.href = `/video?q=${f.slug}`; card.className = 'related-card';
                card.onclick = (e) => { e.preventDefault(); window.history.pushState({}, '', `/video?q=${f.slug}`); routeHandler(); };
                card.innerHTML = `<div class="thumb-wrapper"><img src="${f.thumbnail || FALLBACK_THUMB}" class="thumb-img" onerror="this.src='${FALLBACK_THUMB}'"><div class="type-badge" style="font-size:10px; padding:2px;">${getMediaType(f.mime_type)}</div></div><div class="related-info"><div class="related-title">${f.title}</div><span style="font-size:11px; color:var(--yt-muted);">Vault</span></div>`;
                container.appendChild(card);
            });

            // 2. YT Public Suggest API (JSONP Injection)
            if(queryText.length > 3) {
                const script = document.createElement('script');
                window.ytSuggestCallback = function(data) {
                    if(data && data[1]) {
                        data[1].slice(0, 5).forEach(suggestion => {
                            const sc = document.createElement('a');
                            sc.className = 'related-card'; sc.href = "#";
                            sc.onclick = (e) => { e.preventDefault(); document.getElementById('searchInput').value = suggestion[0]; handleSearch(); };
                            sc.innerHTML = `<div class="thumb-wrapper" style="background:#333; display:flex; align-items:center; justify-content:center; font-size:24px;">🔍</div><div class="related-info"><div class="related-title" style="text-transform:capitalize;">${suggestion[0]}</div><div class="yt-pill">YouTube Query</div></div>`;
                            container.appendChild(sc);
                        });
                    }
                };
                script.src = `https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q=${encodeURIComponent(queryText)}&callback=ytSuggestCallback`;
                document.body.appendChild(script);
            }
        }

        function toggleTheater() { document.getElementById('watchView').classList.toggle('theater-mode'); window.scrollTo({top: 0, behavior: 'smooth'}); }
        async function togglePiP() {
            const video = document.getElementById('mainMedia');
            if(!video || video.tagName !== 'VIDEO') return;
            if (document.pictureInPictureElement) await document.exitPictureInPicture();
            else await video.requestPictureInPicture();
        }

        init();
        window.onpopstate = routeHandler;
    </script>
</body>
</html>
"""

@app.get("/view", response_class=HTMLResponse)
@app.get("/video", response_class=HTMLResponse)
async def serve_media_tube():
    return HTMLResponse(content=MEDIA_TUBE_HTML)