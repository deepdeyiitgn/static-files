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
# 🛡️ FIX: Force Python to recognize WebP, SVG, and GIF as images
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('image/gif', '.gif')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("QlynkHost")

HF_TOKEN = os.environ.get("HF_TOKEN")
SPACE_PASSWORD = os.environ.get("SPACE_PASSWORD")

# 🛡️ SECURITY SWITCH: CDN Mode vs High-Security Mode
# True = Slugs rotate automatically (Best for private vaults)
# False = Links are permanent (Best for CDN & Profile Pics)
# 🛡️ CDN MODE CONFIGURATION
# Set to 'false' in Hugging Face Secrets if using as a permanent CDN for websites
AUTO_SLUG_ROTATOR = str(os.environ.get("AUTO_SLUG_ROTATOR", "true")).lower() == "true"

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

    # 💾 YEH NAYA BLOCK (Memory Restore)
    try:
        session_file = "qlynk_userbot.session" if os.environ.get("TG_SESSION_STRING") else "qlynk_bot.session"
        session_path = hf_hub_download(repo_id=DATASET_REPO, filename=session_file, repo_type="dataset", token=HF_TOKEN)
        shutil.copy(session_path, session_file)
        logger.info("💾 Telegram Session Memory Restored from Vault.")
    except EntryNotFoundError:
        logger.warning("No Telegram Session memory found. Will start fresh and learn IDs.")
    except Exception as e:
        pass
        
    # --- ENTERPRISE BACKGROUND TASKS --- # <--- YEH NAYI LINE ADD KAR DE
    asyncio.create_task(media_optimizer_loop())
# --- ENTERPRISE BACKGROUND TASKS ---
  #  asyncio.create_task(media_optimizer_loop())
    
    # Start Rotator only if not disabled (For CDN Mode)
    if AUTO_SLUG_ROTATOR:
        logger.info("🛡️ Dynamic Slug Rotator is ENABLED.")
        asyncio.create_task(dynamic_slug_rotator())  # <--- YEH NAYI LINE ADD KAR DE
    else:
        logger.info("⚡ CDN Mode Active: Dynamic Slug Rotator is DISABLED.")
    
    # --- START BOT ---  
    
    # --- START BOT ---
    if TG_API_ID != 0 and TG_BOT_TOKEN != "dummy":
        await tg_app.start()
        logger.info("🤖 Pyrogram Max Power MTProto Bot Started!")
    
    yield
    
    # --- SHUTDOWN SEQUENCE ---
    if TG_API_ID != 0 and TG_BOT_TOKEN != "dummy":
        await tg_app.stop()
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
# 4. UTILITY & SMART CACHED DATABASE FUNCTIONS
# ==========================================
import time

def format_size(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

# 🧠 RAM Cache Engine (Prevents 1000+ API calls)
DB_CACHE = {
    "history": {"data": None, "last_sync": 0},
    "tokens": {"data": None, "last_sync": 0},
    "subtitles": {"data": None, "last_sync": 0}
}
CACHE_TTL = 300 # 5 Minutes Sync Timer

def get_db() -> Dict[str, Any]:
    # Sirf tab API call karega jab Cache khali ho ya 5 minute ho gaye hon
    if DB_CACHE["history"]["data"] is None or time.time() - DB_CACHE["history"]["last_sync"] > CACHE_TTL:
        try:
            file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
            with open(file_path, "r") as f:
                DB_CACHE["history"]["data"] = json.load(f)
            DB_CACHE["history"]["last_sync"] = time.time()
        except Exception as e:
            logger.error(f"Database Read Error: {e}")
            if DB_CACHE["history"]["data"] is None:
                return {"total_files": 0, "total_size_bytes": 0, "files": []}
    return DB_CACHE["history"]["data"]

def save_db(db_data: Dict[str, Any]):
    db_data["total_files"] = len(db_data.get("files", []))
    db_data["total_size_bytes"] = sum(item.get("size_bytes", 0) for item in db_data.get("files", []))
    
    with open("history.json", "w") as f:
        json.dump(db_data, f, indent=4)
        
    api.upload_file(
        path_or_fileobj="history.json", path_in_repo="history.json", 
        repo_id=DATASET_REPO, repo_type="dataset"
    )
    # ⚡ Update RAM instantly so no API call is needed after saving
    DB_CACHE["history"]["data"] = db_data
    DB_CACHE["history"]["last_sync"] = time.time()

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
    # 1. Check URL Progress Tracker (For YT-DLP & Direct Links)
    if task_id in url_progress_tracker:
        data = url_progress_tracker[task_id]
        status = data.get("status", "")
        
        # Smart Status Mapping for Frontend
        if status == "error": return {"progress": 100.0, "status": "fallback"} # Fake 100% to safely close loader
        if status == "done": return {"progress": 100.0, "status": "success"}
        if status == "uploading_to_hf": return {"progress": 99.0, "status": "syncing"}
        if status == "processing_media": return {"progress": 95.0, "status": "optimizing"}
            
        total = data.get("total", 0)
        loaded = data.get("loaded", 0)
        if total > 0:
            prog = round((loaded / total) * 90, 2)
            return {"progress": prog, "status": "downloading"}
            
        return {"progress": 5.0, "status": "initializing"}
        
    # 2. Fallback to Local File Upload Tracker
    return {"progress": progress_store.get(task_id, 0.0), "status": "uploading"}
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
    
    final_slug = slug.strip() if slug and slug.strip() != "" else uuid.uuid4().hex
    
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
# 🌟 THE PURE TERMINAL ENGINE (IPv4 Datacenter Fix) 🌟
                ydl_opts = {
                    'outtmpl': f'/tmp/{final_slug}_media.%(ext)s',
                    'progress_hooks': [ytdl_progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'socket_timeout': 25,  # 👈 REDUCED TO 15s so it fails faster if blocked
                    'force_ipv4': True,  
                    'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
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

                def download_yt():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(link_url, download=True)
                        return info.get('thumbnail'), info.get('title')
                
                try:
                    # 🚀 THE SMART FIREWALL: 
                    # Hard timeout hata diya. Ab yt-dlp ka internal 'socket_timeout' kaam karega.
                    # Agar download chal raha hai, toh pura time lega. Agar HF block karega (hang hoga), toh 15s mein fallback chalega!
                    extracted_thumb, extracted_title = await asyncio.to_thread(download_yt)
                except Exception as e:
                    # Connection block hone par exception aayegi aur turant 308 link save hoga
                    raise Exception(f"YT-DLP Failed or Blocked (Moving to 308 Fallback): {e}")

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
            
            # 🚀 SMART METADATA RECOVERY
            yt_id_match = re.search(r"(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})", link_url)
            
            if yt_id_match:
                yt_id = yt_id_match.group(1)
                filename = f"YouTube_{yt_id}"
                extracted_thumb = f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg"
                
                # Try to get Actual YouTube Title
                if not title:
                    try:
                        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={yt_id}&format=json"
                        async with aiohttp.ClientSession() as session:
                            async with session.get(oembed_url, timeout=5) as resp:
                                if resp.status == 200:
                                    o_json = await resp.json()
                                    title = o_json.get("title")
                    except: pass
                
                # Fallback if YouTube OEmbed fails
                if not title: title = f"YouTube Video [{yt_id}]"
            else:
                # 🔗 IDENTICAL/UNIDENTICAL NON-YOUTUBE LINKS
                filename = "External_Resource"
                # User's specific format: EXTERNAL_URL[LINK HERE]
                if not title: 
                    title = f"EXTERNAL_URL[{link_url}]"
                
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
# 5.5 ENTERPRISE TOKENIZED STREAMING (TIME-LIMITED SECURE ROUTES)
# ==========================================
# In-memory store for active stream sessions
stream_sessions = {}

@app.get("/api/stream/generate/{slug}")
async def generate_secure_stream(slug: str, request: Request):
    """Generates a temporary, 4-hour valid unique streaming link."""
    
    # 🛡️ THE GUEST & ADMIN VERIFIER FIX 🛡️
    auth_token = request.cookies.get("auth_token")
    share_token = request.cookies.get("share_token")
    
    if auth_token and auth_token == os.environ.get("SPACE_PASSWORD"):
        pass # Admin has full access
    elif share_token:
        db = get_tokens_db()
        token_data = db["tokens"].get(share_token)
        if not token_data or time.time() > token_data["expires_at"]:
            raise HTTPException(status_code=401, detail="Premium Access Expired")
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_id = uuid.uuid4().hex
    
    # Expiry set to 4 hours (14400 seconds) from now
    stream_sessions[session_id] = {
        "slug": slug,
        "expires": time.time() + 14400,
        "ip": request.client.host # IP binding for extra security
    }
    
    # Periodic Cleanup of old tokens
    current_time = time.time()
    expired_keys = [k for k, v in stream_sessions.items() if v["expires"] < current_time]
    for k in expired_keys: del stream_sessions[k]
        
    return {"status": "success", "stream_url": f"/stream/media/{session_id}"}

@app.get("/stream/media/{session_id}")
async def serve_secure_stream(session_id: str, request: Request):
    """Serves the actual file securely with Anti-Download and Rolling Expiry."""
    session = stream_sessions.get(session_id)
    
    # 1. STRICT EXPIRY CHECK & TARPIT DEFENSE
    if not session or time.time() > session["expires"]:
        # Token expired ya galat hai -> Tarpit defense (Fake garbage data)
        await asyncio.sleep(2)
        return Response(content=os.urandom(1024), media_type="application/octet-stream", status_code=403)
        
    # 2. ANTI-DIRECT DOWNLOAD FIREWALL (Header Inspection)
    # Check if request is coming from a <video> tag or direct browser hit
    fetch_dest = request.headers.get("sec-fetch-dest", "")
    
    # Agar koi direct link kholta hai toh usko redirect karke Player UI par bhej do
    if fetch_dest == "document" or fetch_dest == "":
        return RedirectResponse(url=f"/video?q={session['slug']}", status_code=302)

    # Agar request audio/video tag se NAHI aa rahi hai (e.g. IDM download)
    if fetch_dest not in ["video", "audio", "empty"]:
        return Response(content=b"Direct downloading strictly prohibited.", status_code=403)

    # 3. ROLLING EXPIRY (Auto-renew session while watching)
    # Har active chunk request par expiry ko agle 2 ghante ke liye extend kar do!
    # Toh 4-hour wali video beech mein kabhi crash nahi hogi.
    session["expires"] = time.time() + 7200 # 2 Hours from last chunk loaded

    slug = session["slug"]
    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="Media asset not found in Vault.")

    # 4. SERVE THE FILE SECURELY (Hugging Face Hub)
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename=file_record["path"], repo_type="dataset", token=HF_TOKEN)
        return FileResponse(
            path=file_path, 
            filename=file_record["filename"],
            media_type=file_record.get("mime_type", "application/octet-stream"),
            content_disposition_type="inline" # Forces inline play, strict no-attachment
        )
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return Response(content=os.urandom(1024), status_code=500)
        
# ==========================================
# 6. PUBLIC CONTENT DELIVERY NETWORK (CDN) [HONEYPOT ENGINE]
# ==========================================
import random
import os
from fastapi.responses import Response

# --- 1. ADD THIS GLOBAL DICTIONARY HERE ---
# This keeps track of how many times an IP has guessed wrong
ip_strikes = {}

# --- 2. REPLACE THE FUNCTION WITH THIS UPDATED VERSION ---
@app.get("/f/{slug:path}")
async def serve_file_publicly(slug: str, request: Request): # Notice 'request: Request' is added here!
    client_ip = request.client.host
    
    # [THE BLACK HOLE] 
    # If this IP has failed more than 20 times, they are a scanner.
    if ip_strikes.get(client_ip, 0) > 20:
        # Hold their connection open for 5 minutes to crash their script's RAM
        await asyncio.sleep(300) 
        return Response(status_code=403, content="Blocked by Omniscient Engine.")

    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    # [ADAPTIVE TARPIT & HONEYPOT] - Fake File Logic
    if not file_record:
        # Add a strike to this IP
        ip_strikes[client_ip] = ip_strikes.get(client_ip, 0) + 1
        current_strikes = ip_strikes[client_ip]
        
        # Exponential sleep: 1st strike = 2s, 5th strike = 10s, 10th strike = 20s
        penalty_time = float(current_strikes * 2.0)
        await asyncio.sleep(penalty_time)
        
        # Generate Fake File
        fake_size = random.randint(10240, 102400)
        fake_bytes = os.urandom(fake_size)
        fake_types = ["image/jpeg", "video/mp4", "application/zip", "application/pdf", "audio/mpeg"]
        
        return Response(
            content=fake_bytes, 
            media_type=random.choice(fake_types), 
            status_code=200,
            headers={"Cache-Control": "public, max-age=86400"} # Matches real files (Phase 2 Fix)
        )
        
    # [LEGITIMATE USER LOGIC]
        # If they successfully requested a real file, reset their strikes to 0
        if client_ip in ip_strikes:
            ip_strikes[client_ip] = 0

        # Handle external redirects (Social links)
        # Handle external redirects (Social links)
        # Handle external redirects (Social links)
        if file_record.get("is_external") and file_record.get("external_url"):
            return RedirectResponse(url=file_record["external_url"], status_code=308)
            
        # 🛡️ THE IDEA 1.5 SMART COOKIE FIREWALL (Ultimate Edition) 🛡️
        auth_cookie = request.cookies.get("auth_token", "")
        is_admin = (auth_cookie == os.environ.get("SPACE_PASSWORD")) and bool(os.environ.get("SPACE_PASSWORD"))
        
        # FIX: Bulletproof string conversion to prevent 'NoneType' silent crashes (The 206 Bypass)
        mime = str(file_record.get("mime_type") or "").lower()
        fname = str(file_record.get("filename") or "").lower()
        is_media = mime.startswith(("video/", "audio/")) or fname.endswith((".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".mp3", ".wav", ".m4a", ".aac"))
        
        # 🔥 CRITICAL 206 BYPASS FIX (V8): The "No-Mercy" Firewall
        # 1. Check if the file is Video or Audio
        mime = str(file_info.get("mime_type", "")).lower() if file_info else ""
        filename = str(file_info.get("name", "")).lower() if file_info else ""
        
        is_video_or_audio = (
            mime.startswith("video/") or 
            mime.startswith("audio/") or 
            filename.endswith((".mp4", ".mkv", ".webm", ".avi", ".ts", ".mp3", ".m4a", ".wav", ".flac", ".ogg"))
        )
        
        # 2. THE ULTIMATE BLOCK:
        # Tera native player video chalane ke liye /stream/media/{token} use karta hai, /f/{slug} nahi!
        # Toh agar koi bhi (jo Admin nahi hai) is /f/ share link pe aayega, usko 100% Timer UI dikhega.
        # IDM ho, Incognito ho, ya direct paste — sab block honge!
        if is_video_or_audio and not is_admin:
            # STRICT BLOCK: Nice HTML UI + 7s Timer + Social Routes
            html_page = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="refresh" content="7;url=/video?q={slug}">
                <title>Secure Routing | Qlynk Node</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
                    body {{ background: #050505; color: #e1e4e8; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; text-align: center; }}
                    .container {{ border: 1px solid #30363d; background: rgba(22, 27, 34, 0.8); padding: 40px 30px; border-radius: 16px; max-width: 480px; width: 100%; box-shadow: 0 20px 40px rgba(0,0,0,0.6); backdrop-filter: blur(10px); }}
                    .logo {{ width: 65px; height: 65px; margin-bottom: 15px; filter: drop-shadow(0 0 10px rgba(188, 140, 255, 0.5)); }}
                    h2 {{ color: #bc8cff; margin: 0 0 10px 0; font-size: 22px; }}
                    p {{ color: #8b949e; font-size: 14px; margin-bottom: 20px; line-height: 1.5; }}
                    .features {{ text-align: left; background: #0d1117; padding: 15px; border-radius: 8px; font-size: 13px; color: #c9d1d9; margin-bottom: 20px; border: 1px solid #30363d; }}
                    .features strong {{ color: #58a6ff; display: block; margin-bottom: 8px; }}
                    .features ul {{ margin: 0; padding-left: 20px; }}
                    .features li {{ margin-bottom: 5px; }}
                    .timer-box {{ background: #161b22; border: 1px solid #30363d; padding: 12px; border-radius: 8px; font-weight: 600; color: #8b949e; font-size: 15px; margin-bottom: 25px; }}
                    .timer-box span {{ font-size: 20px; color: #bc8cff; font-weight: 800; }}
                    .social-links {{ display: flex; justify-content: center; gap: 10px; margin-bottom: 25px; flex-wrap: wrap; }}
                    .social-links a {{ color: #e1e4e8; text-decoration: none; font-size: 13px; background: #21262d; padding: 8px 15px; border-radius: 20px; transition: 0.3s; border: 1px solid #30363d; font-weight: 600; }}
                    .social-links a:hover {{ background: #bc8cff; color: #000; border-color: #bc8cff; }}
                    .redirect-btn {{ display: inline-block; padding: 12px 25px; background: #e1e4e8; color: #000; text-decoration: none; border-radius: 8px; font-weight: bold; transition: 0.3s; width: 100%; box-sizing: border-box; }}
                    .redirect-btn:hover {{ background: #bc8cff; box-shadow: 0 0 15px rgba(188, 140, 255, 0.4); }}
                </style>
            </head>
            <body>
                <div class="container">
                    <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="Qlynk Logo" class="logo">
                    <h2>Secure Datacenter Routing</h2>
                    <p>Direct raw access is blocked to protect bandwidth. You are being securely routed to the <b>Cinematic Player UI</b>.</p>
                    
                    <div class="features">
                        <strong>⚡ Why use the Player?</strong>
                        <ul>
                            <li>Hardware Accelerated No-Lag Streaming</li>
                            <li>Subtitle (CC) & Theater Mode Support</li>
                            <li>100% Ad-Free & Encrypted Environment</li>
                        </ul>
                    </div>

                    <div class="timer-box">
                        Routing to Vault in <span id="time">7</span>s...
                    </div>
                    
                    <div class="social-links">
                        <a href="/instagram" target="_blank">Instagram</a>
                        <a href="/github" target="_blank">GitHub</a>
                        <a href="/discord" target="_blank">Discord</a>
                        <a href="/youtube" target="_blank">YouTube</a>
                        <a href="/wiki" target="_blank">Wiki</a>
                        <a href="/clock" target="_blank">Clock</a>
                    </div>

                    <a href="/video?q={slug}" class="redirect-btn">Force Route Now</a>
                </div>
                <script>
                    let sec = 7;
                    const timerEl = document.getElementById('time');
                    const interval = setInterval(() => {{
                        sec--;
                        if(sec > 0) timerEl.innerText = sec;
                        else clearInterval(interval);
                    }}, 1000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(
                status_code=403, 
                content=html_page,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
            )
            
        # [REAL FILE DELIVERY]
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename=file_record["path"], repo_type="dataset", token=HF_TOKEN)
        
        # 🛡️ FIX: Force correct mime-type for browser rendering (Fixes even old uploaded files)
        serve_mime = file_record.get("mime_type", "application/octet-stream")
        fname_lower = file_record["filename"].lower()
        if fname_lower.endswith('.webp'): serve_mime = "image/webp"
        elif fname_lower.endswith('.svg'): serve_mime = "image/svg+xml"
        elif fname_lower.endswith('.gif'): serve_mime = "image/gif"
        
        return FileResponse(
            path=file_path, filename=file_record["filename"],
            media_type=serve_mime, content_disposition_type="inline",
            headers={"Cache-Control": "public, max-age=86400"} 
        )
    except Exception as e:
        logger.error(f"Error serving file '{slug}': {e}")
        await asyncio.sleep(random.uniform(1.0, 3.0))
        return Response(
            content=os.urandom(10240), 
            media_type="application/octet-stream", 
            status_code=200,
            headers={"Cache-Control": "public, max-age=86400"}
        )

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
from datetime import datetime

# Virtual Cache in-memory store
sitemap_cache = {
    "content": "",
    "last_generated": 0
}

async def generate_sitemap(request: Request):
    try:
        logger.info("Generating Sitemap for cache...")
        
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
        social_links = ["/instagram", "/github", "/discord", "/youtube", "/wiki", "/status", "/clock", "/terms", "/privacy", "/refund", "/21"]
        for link in social_links:
            urls.append(f"""
            <url>
                <loc>https://static.qlynk.me{link}</loc>
                <lastmod>{current_time}</lastmod>
                <changefreq>weekly</changefreq>
                <priority>0.7</priority>
            </url>
            """)
            
        # NOTE: File indexing (history.json) removed for Vault Privacy & Security.
            
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
        # Background task sirf tabhi start hogi jab sitemap pehli baar hit ho
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
from fastapi.responses import HTMLResponse, FileResponse, Response
from typing import Dict, Any
import time
import uuid
import json
import os
import re
from datetime import datetime
from huggingface_hub import hf_hub_download

# --- 🧠 Persistent Token Store & Subtitle DB Managers ---

# Database loader for Share Tokens
# --- SHARE TOKENS DATABASE (CACHED) ---
def get_tokens_db() -> Dict[str, Any]:
    if DB_CACHE["tokens"]["data"] is None or time.time() - DB_CACHE["tokens"]["last_sync"] > CACHE_TTL:
        try:
            file_path = hf_hub_download(repo_id=DATASET_REPO, filename="share_tokens.json", repo_type="dataset", token=HF_TOKEN)
            with open(file_path, "r") as f:
                DB_CACHE["tokens"]["data"] = json.load(f)
            DB_CACHE["tokens"]["last_sync"] = time.time()
        except Exception:
            if DB_CACHE["tokens"]["data"] is None:
                return {"tokens": {}}
    return DB_CACHE["tokens"]["data"]

def save_tokens_db(db_data: Dict[str, Any]):
    with open("share_tokens.json", "w") as f:
        json.dump(db_data, f, indent=4)
    api.upload_file(path_or_fileobj="share_tokens.json", path_in_repo="share_tokens.json", repo_id=DATASET_REPO, repo_type="dataset")
    DB_CACHE["tokens"]["data"] = db_data
    DB_CACHE["tokens"]["last_sync"] = time.time()

# --- SUBTITLE DATABASE (CACHED) ---
def get_sub_db() -> Dict[str, Any]:
    if DB_CACHE["subtitles"]["data"] is None or time.time() - DB_CACHE["subtitles"]["last_sync"] > CACHE_TTL:
        try:
            file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history_subtitle.json", repo_type="dataset", token=HF_TOKEN)
            with open(file_path, "r") as f:
                DB_CACHE["subtitles"]["data"] = json.load(f)
            DB_CACHE["subtitles"]["last_sync"] = time.time()
        except Exception:
            if DB_CACHE["subtitles"]["data"] is None:
                return {"subtitles": []}
    return DB_CACHE["subtitles"]["data"]

def save_sub_db(db_data: Dict[str, Any]):
    with open("history_subtitle.json", "w") as f:
        json.dump(db_data, f, indent=4)
    api.upload_file(path_or_fileobj="history_subtitle.json", path_in_repo="history_subtitle.json", repo_id=DATASET_REPO, repo_type="dataset")
    DB_CACHE["subtitles"]["data"] = db_data
    DB_CACHE["subtitles"]["last_sync"] = time.time()

# --- 🔒 Dual-Auth Verifier (Persistent) ---
def verify_view_access(password: str = Header(None), auth_token: str = Cookie(None), share_token: str = Cookie(None)):
    admin_token = password or auth_token
    if admin_token and admin_token == SPACE_PASSWORD:
        return {"role": "admin"}
        
    if share_token:
        db = get_tokens_db()
        token_data = db["tokens"].get(share_token)
        
        if token_data:
            current_time = time.time()
            
            # Check if token is still within its 24-hour window
            if current_time < token_data["expires_at"]:
                # Agar active nahi mark kiya hai ti active kar do
                if token_data.get("status") != "active":
                    token_data["status"] = "active"
                    save_tokens_db(db)
                return {"role": "guest"}
            else:
                # Token ka time khtam ho gaya hai, isko permanently 'expired' mark karo (delete nahi)
                if token_data.get("status") != "expired":
                    token_data["status"] = "expired"
                    save_tokens_db(db)
                    
    raise HTTPException(status_code=401, detail="Access Expired or Denied.")

# --- 🔗 Share Token API (Persistent) ---
@app.post("/api/share/generate")
async def generate_share_token(token: str = Depends(verify_auth)):
    new_token = uuid.uuid4().hex
    
    db = get_tokens_db()
    # 86400 seconds = 24 Hours TTL
    db["tokens"][new_token] = {
        "expires_at": time.time() + 86400,
        "status": "active",
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    save_tokens_db(db)
    
    return {"status": "success", "share_token": new_token}

# --- 📁 Media Library API ---
# --- 📁 Media Library API ---
@app.get("/api/media_library")
async def fetch_media_library(access: dict = Depends(verify_view_access)):
    db = get_db()
    filtered_files = []
    for f in db.get("files", []):
        mime = str(f.get("mime_type", ""))
        is_ext = f.get("is_external", False)
        ext_url = str(f.get("external_url", ""))
        
        # Rule: Local media ko allow karo, YA phir YouTube external links ko allow karo
        if (not is_ext and mime.startswith(("video/", "audio/"))) or (is_ext and ("youtube.com" in ext_url or "youtu.be" in ext_url)):
            filtered_files.append(f)
            
    return sorted(filtered_files, key=lambda x: x.get("uploaded_at", ""), reverse=True)

# --- 📝 Subtitle Upload API (Raw Safe Save) ---
@app.post("/api/subtitle/upload")
async def upload_subtitle(
    file: UploadFile = File(...),
    media_slug: str = Form(...),
    language: str = Form(...),
    token: str = Depends(verify_auth)
):
    ext = ".srt" if file.filename.lower().endswith(".srt") else ".vtt"
    sub_slug = str(uuid.uuid4())[:8]
    filename = f"{language.lower()}_{sub_slug}{ext}"
    temp_path = f"/tmp/{filename}"
    repo_path = f"subtitles/{filename}"
    
    # Save exactly as it is (Raw Bytes, No corruption)
    with open(temp_path, "wb") as f:
        content = await file.read()
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
    
    return {"status": "success", "message": f"Subtitle ({language}) safely saved as {ext}!"}

# Fixed parameter path capturing for slugs with slashes
@app.get("/api/subtitles/list/{media_slug:path}")
async def list_subtitles(media_slug: str, access: dict = Depends(verify_view_access)):
    db = get_sub_db()
    return [s for s in db.get("subtitles", []) if s["media_slug"] == media_slug]

# --- 🎬 Subtitle Serve API (On-the-fly Browser Converter) ---
@app.get("/sub/{sub_slug}")
async def serve_subtitle_file(sub_slug: str):
    db = get_sub_db()
    sub_record = next((s for s in db.get("subtitles", []) if s["sub_slug"] == sub_slug), None)
    if not sub_record: raise HTTPException(status_code=404, detail="Subtitle not found.")
    
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename=sub_record["path"], repo_type="dataset", token=HF_TOKEN)
        
        # Directly serve if it's already VTT
        if sub_record["path"].endswith(".vtt"):
            return FileResponse(path=file_path, media_type="text/vtt")
            
        # Convert SRT to VTT purely on-the-fly for the browser
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            srt_content = f.read()
            
        vtt_content = "WEBVTT\n\n" + re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_content)
        return Response(content=vtt_content, media_type="text/vtt")
        
    except Exception as e: 
        logger.error(f"Subtitle Error: {e}")
        raise HTTPException(status_code=500, detail="Error loading subtitle file.")

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

        /* Skeleton Loading UI */
        .skeleton-anim { background: linear-gradient(90deg, #222 25%, #333 50%, #222 75%); background-size: 200% 100%; animation: loadingShimmer 1.5s infinite linear; }
        @keyframes loadingShimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }

        .watch-layout { display: flex; gap: 24px; flex-wrap: wrap; }
        .primary-col { flex: 1; min-width: 65%; max-width: 1200px; }
        .secondary-col { width: 350px; flex-shrink: 0; display: flex; flex-direction: column; gap: 15px;}
        
        /* PLAYER ARCHITECTURE */
        .player-wrapper { width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 12px; overflow: hidden; position: relative; box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center;}
        .player-element { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain; z-index: 5; display: block;}
        .yt-container { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 4;}
        
        /* Video Loading Spinner (SVG YouTube Style) */
        .loader-spinner { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 65px; height: 65px; z-index: 10; pointer-events: none; display: none; }
        .loader-spinner svg { animation: yt-spin 2s linear infinite; width: 100%; height: 100%; }
        .loader-spinner .path { stroke: var(--yt-brand); stroke-linecap: round; animation: yt-dash 1.5s ease-in-out infinite; }
        @keyframes yt-spin { 100% { transform: rotate(360deg); } }
        @keyframes yt-dash { 0% { stroke-dasharray: 1, 150; stroke-dashoffset: 0; } 50% { stroke-dasharray: 90, 150; stroke-dashoffset: -35; } 100% { stroke-dasharray: 90, 150; stroke-dashoffset: -124; } }

        /* Audio Visuals */
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .audio-disc { width: 250px; height: 250px; border-radius: 50%; object-fit: cover; border: 4px solid var(--yt-brand); animation: spin 8s linear infinite; animation-play-state: paused; z-index: 6; box-shadow: 0 0 40px rgba(0,0,0,0.8); display: block; transition: border-color 0.3s;}
        .audio-disc.playing { animation-play-state: running; }
        .audio-visualizer { position: absolute; bottom: 0; left: 0; width: 100%; height: 100%; z-index: 4; pointer-events: none;}
        
        /* Action UI Overlay */
        .action-icon-overlay { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.7); color: #fff; padding: 20px 30px; border-radius: 50px; font-size: 32px; font-weight: bold; z-index: 80; opacity: 0; pointer-events: none; display: flex; align-items: center; gap: 15px; transition: opacity 0.2s, transform 0.2s; backdrop-filter: blur(5px);}
        .action-icon-overlay.show { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
        .fast-forward-overlay { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: #fff; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: bold; z-index: 100; display: none; pointer-events: none; align-items: center; gap: 8px;}
        
        .custom-controls { position: absolute; bottom: 0; left: 0; width: 100%; padding: 60px 20px 10px 20px; background: linear-gradient(transparent, rgba(0,0,0,0.95)); z-index: 50; display: flex; flex-direction: column; gap: 8px; opacity: 0; transition: opacity 0.3s;}
        /* 🛡️ FIX: Removed hover force-show for proper JS auto-hide control */
        .custom-controls.active { opacity: 1; }
        
        /* 🚀 FIX: YOUTUBE STYLE SEEK BAR (Gray Buffer + Progress Circle) */
        .seek-container { width: 100%; height: 5px; background: rgba(255,255,255,0.2); border-radius: 3px; cursor: pointer; position: relative; transition: height 0.1s; touch-action: none; display: flex; align-items: center;}
        .seek-container:hover { height: 8px; }
        .seek-buffer { position: absolute; top: 0; left: 0; height: 100%; background: rgba(255,255,255,0.4); border-radius: 3px; width: 0%; pointer-events: none; transition: width 0.3s;}
        .seek-progress { position: absolute; top: 0; left: 0; height: 100%; background: var(--yt-brand); border-radius: 3px; width: 0%; pointer-events: none; display: flex; justify-content: flex-end; align-items: center;}
        /* YouTube jaisa Circle (Thumb) jo hover karne par pop hoga */
        .seek-progress::after { content: ''; width: 14px; height: 14px; background: var(--yt-brand); border-radius: 50%; margin-right: -7px; transform: scale(0); transition: transform 0.2s; box-shadow: 0 0 5px rgba(0,0,0,0.5); }
        .seek-container:hover .seek-progress::after { transform: scale(1); }
        
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
        
        /* ACTIVE SUBTITLE TICK MARK */
        .active-cc { color: var(--yt-brand); font-weight: bold; }
        .active-cc::after { content: ' ✔'; }

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
        ::cue { background-color: rgba(0,0,0,0.8); color: white; font-family: sans-serif; }

        @media(max-width: 1000px) { .primary-col { min-width: 100%; } .secondary-col { width: 100%; } .search-box { width: 60%; } }
        @media(max-width: 600px) { 
            .search-box { display: flex; flex: 1; margin: 0 10px; } 
            .logo span { display: none; } 
            .search-box input { font-size: 12px; padding: 8px 10px; } 
            .search-box button { padding: 8px 12px; } 
            .custom-controls { padding: 40px 10px 10px 10px;} 
            .ctrl-btn { font-size: 16px;} 
            .volume-slider{ display:none; } 
        }
    </style>
</head>
<body>

    <div class="navbar">
        <div class="logo" onclick="goHome()">▶ <span id="brandLogo">Qlynk</span>Tube</div>
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
        <div id="homeView" class="video-grid"></div>

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
                    <div id="subsList" style="margin-bottom: 10px; color: var(--yt-brand); font-size:12px;"></div>
                    <p>Protected by Qlynk Universal Engine. Native & Hybrid YouTube parsing active. Advanced UI, Subtitle Scaling (+/- keys), Repeat, Shuffle, and Spacebar Logic supported.</p>
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
        // --- SKELETON LOADING (ON BOOT) ---
        function renderSkeleton() {
            document.getElementById('watchView').classList.add('hidden');
            const grid = document.getElementById('homeView');
            grid.classList.remove('hidden');
            grid.innerHTML = '';
            for(let i=0; i<12; i++) {
                grid.innerHTML += `
                    <div class="vid-card">
                        <div class="thumb-wrapper skeleton-anim"></div>
                        <div class="vid-title skeleton-anim" style="height:16px; margin-bottom:8px; border-radius:4px; width:90%;"></div>
                        <div class="vid-meta skeleton-anim" style="height:12px; width:60%; border-radius:4px;"></div>
                    </div>`;
            }
        }
        renderSkeleton(); // Show immediately while script starts up

        // --- AUTH & INITIALIZATION ---
        const urlParams = new URLSearchParams(window.location.search);
        const tokenFromUrl = urlParams.get('token');
        if (tokenFromUrl) {
            document.cookie = "share_token=" + tokenFromUrl + "; path=/; max-age=86400";
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        const isAdmin = document.cookie.includes('auth_token=');

        const FALLBACK_THUMB = "https://qlynk.vercel.app/Quicklink-Banner.png";
       // 💿 Animated Default Artwork (Pulsating & Rotating) - Fully URL Encoded for 100% Browser Support
        const SVG_MUSIC = "data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%3E%3Cdefs%3E%3ClinearGradient%20id%3D%22g%22%20x1%3D%220%25%22%20y1%3D%220%25%22%20x2%3D%22100%25%22%20y2%3D%22100%25%22%3E%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%23bc8cff%22%2F%3E%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%2358a6ff%22%2F%3E%3C%2FlinearGradient%3E%3C%2Fdefs%3E%3Crect%20width%3D%22100%22%20height%3D%22100%22%20fill%3D%22%230f0f0f%22%2F%3E%3Ccircle%20cx%3D%2250%22%20cy%3D%2250%22%20r%3D%2240%22%20fill%3D%22none%22%20stroke%3D%22%23222%22%20stroke-width%3D%223%22%2F%3E%3Ccircle%20cx%3D%2250%22%20cy%3D%2250%22%20r%3D%2230%22%20fill%3D%22none%22%20stroke%3D%22%23333%22%20stroke-width%3D%222%22%20stroke-dasharray%3D%225%205%22%3E%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%2050%2050%22%20to%3D%22360%2050%2050%22%20dur%3D%228s%22%20repeatCount%3D%22indefinite%22%2F%3E%3C%2Fcircle%3E%3Ccircle%20cx%3D%2250%22%20cy%3D%2250%22%20r%3D%2218%22%20fill%3D%22url(%23g)%22%3E%3Canimate%20attributeName%3D%22r%22%20values%3D%2216%3B20%3B16%22%20dur%3D%221.5s%22%20repeatCount%3D%22indefinite%22%2F%3E%3C%2Fcircle%3E%3Ccircle%20cx%3D%2250%22%20cy%3D%2250%22%20r%3D%225%22%20fill%3D%22%23000%22%2F%3E%3C%2Fsvg%3E";
        
        let masterLibrary = [];
        let currentAudioCtx = null;
        let showRemainingTime = false; // ⏳ YouTube-style Time Toggle State
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
        let pendingSubFile = null;
        let ccSize = 100; // Default Subtitle Size (%)

        function formatBytes(bytes) {
            if(bytes === 0) return '0 B';
            const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        // ⏱️ FIX: HH:MM:SS Format Support
        function formatTime(s){
            if(!s || isNaN(s)) return "0:00";
            s = Math.floor(s);
            let h = Math.floor(s / 3600);
            let m = Math.floor((s % 3600) / 60);
            let sec = s % 60;
            if (h > 0) {
                return h + ":" + (m < 10 ? "0" : "") + m + ":" + (sec < 10 ? "0" : "") + sec;
            }
            return m + ":" + (sec < 10 ? "0" : "") + sec;
        }
        function getMediaType(m) {
            if(!m) return 'file'; if(m.startsWith('video/')) return 'video';
            if(m.startsWith('audio/')) return 'audio'; if(m.startsWith('image/')) return 'image';
            return 'file';
        }
        
        // Robust YT Regex
        function extractYtId(url) {
            const patterns = [
                /^(?:https?:\/\/)?(?:m\.|www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))((\w|-){11})(?:\S+)?$/,
                /^((\w|-){11})$/
            ];
            for(let p of patterns) {
                const match = url.trim().match(p);
                if(match) return match[1];
            }
            return null;
        }

        // Dominant Color Engine
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
                } catch(e) { setThemeColor(fallback); }
            };
            img.onerror = () => setThemeColor(fallback);
        }

        function setThemeColor(color) {
            document.documentElement.style.setProperty('--yt-brand', color);
            window.currentThemeColor = color;
        }

        // --- SUBTITLE SCALING LOGIC ---
        function updateCCSize() {
            let styleEl = document.getElementById('dynamic-cc-style');
            if(!styleEl) {
                styleEl = document.createElement('style');
                styleEl.id = 'dynamic-cc-style';
                document.head.appendChild(styleEl);
            }
            styleEl.innerHTML = `
                @media(min-width: 768px) {
                    ::cue { font-size: ${ccSize}% !important; }
                    video::cue { font-size: ${ccSize}% !important; }
                }
            `;
        }

        async function init() {
            try {
                const res = await fetch('/api/media_library');
                if(res.status === 401) return document.getElementById('homeView').innerHTML = "<div style='text-align:center; width:100%; margin-top:50px;'><h2 style='color:var(--yt-muted); margin-bottom:15px;'>🔒 ACCESS DENIED</h2><p style='color:#8b949e; margin-bottom:25px;'>You need an active token to view the cinematic vault.</p><a href='/checkout' style='display:inline-block; background:linear-gradient(45deg, #bc8cff, #58a6ff); color:#000; padding:12px 24px; border-radius:30px; text-decoration:none; font-weight:bold; transition:transform 0.2s;'>Get Premium Access</a></div>";
                
                if(isAdmin) {
                    document.getElementById('shareBtn').style.display = 'block';
                    document.getElementById('addSubBtn').style.display = 'flex';
                } else {
                    document.getElementById('wDownload').style.display = 'none';
                    document.getElementById('addSubBtn').style.display = 'none';
                }
                
                masterLibrary = await res.json();
                routeHandler();
            } catch(e) { document.getElementById('homeView').innerHTML = "<h2 style='color:var(--yt-muted); text-align:center; width:100%;'>Connection Error.</h2>"; }
        }

        function routeHandler() {
            const path = window.location.pathname;
            const params = new URLSearchParams(window.location.search);
            
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
                <div id="loaderSpinner" class="loader-spinner">
                    <svg viewBox="0 0 50 50">
                        <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="4"></circle>
                    </svg>
                </div>
                <div class="action-icon-overlay" id="actionIcon"></div>
                <div class="fast-forward-overlay" id="ffOverlay">Fast Forwarding 2x ▶▶</div>
                <div class="custom-controls" id="pControls">
                    <div class="seek-container" id="pSeek">
                        <div class="seek-buffer" id="pSeekBuf"></div>
                        <div class="seek-progress" id="pSeekProg"></div>
                    </div>
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
        // --- RENDER LOCAL WATCH PAGE ---
        async function renderWatchPage(slug) {
            document.getElementById('homeView').classList.add('hidden');
            document.getElementById('watchView').classList.remove('hidden');
            
            const file = masterLibrary.find(f => f.slug === slug);
            if(!file) return document.getElementById('wTitle').innerText = "File Not Found.";

            // 🚀 NEW LOGIC: Agar yeh database mein external YouTube link hai, toh YouTube player trigger karo!
            if (file.is_external && file.external_url) {
                const ytMatch = extractYtId(file.external_url);
                if (ytMatch) {
                    renderYtPage(ytMatch);
                    return; // Yahin ruk jao, aage local video ka logic mat chalao
                }
            }

            document.getElementById('wTitle').innerText = file.title;
            document.getElementById('wSize').innerText = formatBytes(file.size_bytes);
            document.getElementById('wType').innerText = getMediaType(file.mime_type).toUpperCase();
            document.getElementById('wDate').innerText = `Uploaded on: ${new Date(file.uploaded_at).toLocaleDateString()}`;
            document.getElementById('wDownload').style.display = isAdmin ? 'flex' : 'none';
            document.getElementById('wDownload').href = file.is_external ? file.external_url : `/f/${file.slug}`;
            document.getElementById('addSubBtn').style.display = isAdmin ? 'flex' : 'none';

            const pw = document.getElementById('playerWrapper');
            const type = getMediaType(file.mime_type);
            pw.innerHTML = ''; document.getElementById('videoVisualizer').style.display = 'none';

            let subs = [];
            try { const r = await fetch(`/api/subtitles/list/${encodeURIComponent(slug)}`); if(r.ok) subs = await r.json(); } catch(e){}
            let trackHtml = subs.map((s,i) => `<track kind="subtitles" src="/sub/${s.sub_slug}" srclang="${s.language.substring(0,2).toLowerCase()}" label="${s.language}" ${i===0?'default':''}>`).join('');

            applyDominantColor(file.thumbnail || FALLBACK_THUMB);

            // 🌟 SECURE STREAMING LOGIC START 🌟
            let secureSrc = "";
            if (!file.is_external && type === 'video' || type === 'audio') {
                try {
                    // Chupke se temporary link maango
                    const streamRes = await fetch(`/api/stream/generate/${slug}`);
                    if(streamRes.ok) {
                        const streamData = await streamRes.json();
                        secureSrc = streamData.stream_url; // Yeh /stream/media/xyz123 hoga
                    } else {
                        secureSrc = `/f/${file.slug}`; // Fallback
                    }
                } catch(e) {
                    secureSrc = `/f/${file.slug}`;
                }
            } else {
                secureSrc = file.external_url;
            }
            // 🌟 SECURE STREAMING LOGIC END 🌟

            if(type === 'video') {
                // 🚀 FIX: preload="auto" lagaya for Fast Background Buffering (Safe for Intel UHD graphics)
                pw.innerHTML = `<video id="mainMedia" class="player-element" src="${secureSrc}" crossorigin="anonymous" playsinline preload="auto">${trackHtml}</video>` + getControlsHtml();
                document.getElementById('videoVisualizer').style.display = 'block';
                initVisualizer('mainMedia', 'videoVisualizer', 'bar', window.currentThemeColor);
            } 
            else if(type === 'audio') {
                const thumb = file.thumbnail || SVG_MUSIC;
                pw.innerHTML = `
                    <img id="audioDisc" src="${thumb}" class="audio-disc" onerror="this.src='${SVG_MUSIC}'">
                    <canvas id="audioVisualizer" class="audio-visualizer"></canvas>
                    <audio id="mainMedia" src="${secureSrc}" crossorigin="anonymous" style="display:none;">${trackHtml}</audio>
                ` + getControlsHtml();
                initVisualizer('mainMedia', 'audioVisualizer', 'wave', window.currentThemeColor);
            }
            
            setupMediaSession(file.title, 'Qlynk Vault', file.thumbnail);
            
            // Generate CC List UI
            const ccList = document.getElementById('pCcList');
            if(ccList) {
                ccList.innerHTML = `<div class="setting-item cc-item" id="cc-item--1" onclick="setCC(-1)">Off</div>` + 
                                   subs.map((s,i) => `<div class="setting-item cc-item" id="cc-item-${i}" onclick="setCC(${i})">${s.language}</div>`).join('');
            }

            if(subs.length > 0) {
                document.getElementById('subsList').innerText = `CC Available: ${subs.map(s=>s.language).join(', ')}`;
                updateCCSize(); 
                // Fix: Video load hone ke baad hi CC on hoga
                const mediaCheck = document.getElementById('mainMedia');
                if(mediaCheck) {
                    mediaCheck.addEventListener('loadedmetadata', () => setCC(0), {once: true});
                }
            } else {
                document.getElementById('subsList').innerText = `No Subtitles (CC) linked.`;
                setCC(-1);
            }
            
            const mediaEl = document.getElementById('mainMedia');
            if(mediaEl) {
                // Video Loading Spinner Logic
                const loader = document.getElementById('loaderSpinner');
                mediaEl.addEventListener('waiting', () => { if(loader) loader.style.display = 'block'; });
                mediaEl.addEventListener('playing', () => { if(loader) loader.style.display = 'none'; });
                mediaEl.addEventListener('canplay', () => { if(loader) loader.style.display = 'none'; });

                activePlayer = {
                    play: () => {
                        // 🌊 THE ULTIMATE FIX: Har jagah se Audio Context Resume hoga!
                        if (typeof currentAudioCtx !== 'undefined' && currentAudioCtx && currentAudioCtx.state === 'suspended') {
                            currentAudioCtx.resume();
                        }
                        mediaEl.play();
                    },
                    pause: () => mediaEl.pause(),
                    seek: (t) => { mediaEl.currentTime = t; },
                    setVolume: (v) => { mediaEl.volume = v; mediaEl.muted = false; },
                    toggleMute: () => { mediaEl.muted = !mediaEl.muted; },
                    currentTime: () => mediaEl.currentTime,
                    duration: () => mediaEl.duration || 0,
                    setSpeed: (s) => { mediaEl.playbackRate = s; },
                    isPaused: () => mediaEl.paused,
                    isMuted: () => mediaEl.muted,
                    getVolume: () => mediaEl.volume,
                    getBuffered: () => mediaEl.buffered.length > 0 ? mediaEl.buffered.end(mediaEl.buffered.length - 1) : 0
                };

                mediaEl.play().catch(e => console.log("Autoplay blocked."));
                mediaEl.addEventListener('ended', handleMediaEnded);
                mediaEl.ontimeupdate = updateProgressUI;
                mediaEl.onplay = () => {
                    document.getElementById('pPlay').innerText = '⏸';
                    const disc = document.getElementById('audioDisc');
                    if(disc) disc.classList.add('playing');
                };
                mediaEl.onpause = () => {
                    document.getElementById('pPlay').innerText = '▶';
                    const disc = document.getElementById('audioDisc');
                    if(disc) disc.classList.remove('playing');
                };
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
            applyDominantColor(thumb, '#ff0000');

            const pw = document.getElementById('playerWrapper');
            pw.innerHTML = `<div id="ytContainer" class="yt-container"><div id="ytPlayerDiv" style="width:100%; height:100%;"></div></div>` + getControlsHtml();
            document.getElementById('videoVisualizer').style.display = 'block';

            ytPlayer = new YT.Player('ytPlayerDiv', {
                videoId: ytId,
                width: '100%',
                height: '100%',
                playerVars: { 'autoplay': 1, 'controls': 0, 'disablekb': 1, 'fs': 0, 'rel': 0, 'modestbranding': 1 },
                events: {
                    'onReady': onYtReady,
                    'onStateChange': onYtStateChange
                }
            });
            renderHybridRelated("YouTube Video");
        }

        function onYtReady(event) {
            document.getElementById('wTitle').innerText = ytPlayer.getVideoData().title;
            setupMediaSession(ytPlayer.getVideoData().title, 'YouTube Stream', `https://img.youtube.com/vi/${ytIdActive}/maxresdefault.jpg`);
            
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
                getVolume: () => ytPlayer.getVolume() / 100,
                getBuffered: () => ytPlayer.getVideoLoadedFraction() * (ytPlayer.getDuration() || 0)
            };
            initCustomControls();
            
            const qList = ytPlayer.getAvailableQualityLevels();
            if(qList && qList.length > 0) {
                document.getElementById('ytQualitySection').style.display = 'block';
                document.getElementById('pYtQualityList').innerHTML = qList.map(q => `<button class="btn" style="padding:4px 8px; font-size:11px;" onclick="ytPlayer.setPlaybackQuality('${q}')">${q}</button>`).join('');
            }

            const ccList = document.getElementById('pCcList');
            if(ccList) {
                ccList.innerHTML = `<div class="setting-item cc-item" id="cc-item--1" onclick="ytPlayer.unloadModule('captions'); setCC(-1);">Off</div>
                                    <div class="setting-item cc-item" id="cc-item-0" onclick="ytPlayer.loadModule('captions'); setCC(0);">Auto Enable YT CC</div>`;
                setCC(0);
            }

            ytPollInterval = setInterval(updateProgressUI, 500);
            simulateYtVisualizer();
        }

        function onYtStateChange(event) {
            const pPlay = document.getElementById('pPlay');
            const loader = document.getElementById('loaderSpinner');
            
            if(loader) {
                if (event.data == YT.PlayerState.BUFFERING) loader.style.display = 'block';
                else loader.style.display = 'none';
            }
            
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
                if(ytPlayer && ytPlayer.getPlayerState() !== YT.PlayerState.PLAYING) return;

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

            // ⏳ FIX: Remaining Time Toggle Logic
            let displayTime = "";
            if (showRemainingTime && dur > 0) {
                const remaining = dur - cur;
                displayTime = `-${formatTime(remaining)}`; // Minus lagao
            } else {
                displayTime = formatTime(cur); // Normal current time
            }
            document.getElementById('pTime').innerText = `${displayTime} / ${formatTime(dur)}`;

            // 🚀 Buffer Gray Bar UI Update
            if (activePlayer.getBuffered && dur > 0) {
                const buf = activePlayer.getBuffered();
                const bufPercent = Math.min((buf / dur) * 100, 100);
                const bufEl = document.getElementById('pSeekBuf');
                if(bufEl) bufEl.style.width = `${bufPercent}%`;
            }
        }
        function initCustomControls() {
            const pPlay = document.getElementById('pPlay');
            const pSeek = document.getElementById('pSeek');
            const pVol = document.getElementById('pVol');
            const pMute = document.getElementById('pMute');
            const pw = document.getElementById('playerWrapper');
            const pControls = document.getElementById('pControls');
            const pTime = document.getElementById('pTime');
            // 🖱️ Make time display clickable like YouTube
            pTime.style.cursor = 'pointer';
            pTime.title = 'Click to toggle remaining time';
            pTime.onclick = () => {
                showRemainingTime = !showRemainingTime;
                updateProgressUI(); // Turant update karo
            };
            
            pPlay.onclick = () => {
                // 🛡️ FIX: Browser Autoplay Policy Block. Audio Context ko force-resume karna padega!
                if(window.currentAudioCtx && window.currentAudioCtx.state === 'suspended') {
                    window.currentAudioCtx.resume();
                }
                activePlayer.isPaused() ? activePlayer.play() : activePlayer.pause();
            };
            
            // MOBILE DRAG FIX FOR SEEK BAR
            let isSeeking = false;
            const executeSeek = (e) => {
                const rect = pSeek.getBoundingClientRect();
                let perc = (e.clientX - rect.left) / rect.width;
                perc = Math.max(0, Math.min(1, perc));
                activePlayer.seek(perc * activePlayer.duration());
                document.getElementById('pSeekProg').style.width = `${perc * 100}%`;
            };

            pSeek.addEventListener('pointerdown', (e) => {
                isSeeking = true;
                pSeek.setPointerCapture(e.pointerId);
                executeSeek(e);
            });
            pSeek.addEventListener('pointermove', (e) => {
                if(isSeeking) executeSeek(e);
            });
            pSeek.addEventListener('pointerup', (e) => {
                isSeeking = false;
                pSeek.releasePointerCapture(e.pointerId);
            });

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
            
            document.getElementById('pCC').onclick = (e) => { 
                e.stopPropagation(); 
                document.getElementById('pSettings').classList.toggle('show'); 
            };
            
            document.getElementById('pSetBtn').onclick = (e) => { e.stopPropagation(); document.getElementById('pSettings').classList.toggle('show'); };
            document.getElementById('pSpeedRange').oninput = (e) => { setSpeed(e.target.value); };

            // 🖱️ FIX: YouTube-style Auto Hide (Controls + Mouse Pointer)
            pw.onmousemove = () => {
                pControls.classList.add('active');
                pw.style.cursor = 'default'; // Mouse wapas dikhao
                clearTimeout(controlTimeout);
                
                controlTimeout = setTimeout(() => {
                    // Agar video chal rahi hai (paused nahi hai), tabhi hide kar do
                    if (activePlayer && !activePlayer.isPaused()) {
                        pControls.classList.remove('active');
                        pw.style.cursor = 'none'; // Mouse gayab kar do
                    }
                }, 2500); // 2.5 second idle time
            };

            // Agar mouse player ke bahar chala jaye toh turant hide kar do
            pw.onmouseleave = () => {
                if (activePlayer && !activePlayer.isPaused()) {
                    pControls.classList.remove('active');
                }
            };

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

        // SUBTITLE TICK MARK LOGIC & FORCE SHOW
        window.setCC = function(index) {
            const media = document.getElementById('mainMedia');
            if(media) {
                // Thoda delay diya taaki browser tracks ko DOM mein read kar sake
                setTimeout(() => {
                    if(media.textTracks) {
                        for(let i=0; i<media.textTracks.length; i++) {
                            media.textTracks[i].mode = (i === index) ? 'showing' : 'hidden';
                        }
                    }
                }, 150);
            }
            // Add Checkmark to UI
            document.querySelectorAll('.cc-item').forEach(el => el.classList.remove('active-cc'));
            const activeEl = document.getElementById('cc-item-' + index);
            if(activeEl) activeEl.classList.add('active-cc');
            
            document.getElementById('pSettings').classList.remove('show');
        }

        // --- SPACEBAR PRO & KEYBOARD HUB ---
        document.addEventListener('keydown', (e) => {
            if(document.activeElement.tagName === 'INPUT' || !activePlayer) return;

            if (e.key === '+' || e.key === '=') {
                e.preventDefault();
                ccSize = Math.min(300, ccSize + 25);
                updateCCSize();
                showActionIcon(`💬 CC: ${ccSize}%`);
                return;
            }
            if (e.key === '-' || e.key === '_') {
                e.preventDefault();
                ccSize = Math.max(50, ccSize - 25);
                updateCCSize();
                showActionIcon(`💬 CC: ${ccSize}%`);
                return;
            }

            switch(e.code) {
                case 'Space': 
                    e.preventDefault();
                    if(!e.repeat && spacePressTime === 0) {
                        spacePressTime = Date.now();
                    }
                    if(!isSpaceHolding && spacePressTime > 0 && (Date.now() - spacePressTime > 250)) {
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
            if(document.activeElement.tagName === 'INPUT') return;

            if(e.code === 'Space') {
                e.preventDefault();
                if(isSpaceHolding) {
                    isSpaceHolding = false;
                    activePlayer.setSpeed(normalSpeed);
                    document.getElementById('ffOverlay').style.display = 'none';
                } else if(spacePressTime > 0 && (Date.now() - spacePressTime < 250)) {
                    if(activePlayer) {
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

            const startVisualizer = () => {
                if(currentAudioCtx) {
                    if(currentAudioCtx.state === 'suspended') currentAudioCtx.resume();
                    return;
                }
                try {
                    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    currentAudioCtx = audioCtx;
                    media.crossOrigin = "anonymous";
                    const analyser = audioCtx.createAnalyser();
                    analyser.fftSize = 128; // Waves ko bada aur smooth karne ke liye
                    const source = audioCtx.createMediaElementSource(media);
                    source.connect(analyser); 
                    analyser.connect(audioCtx.destination);
                    const bufferLength = analyser.frequencyBinCount;
                    const dataArray = new Uint8Array(bufferLength);
                    
                    function draw() {
                        currentAnimationId = requestAnimationFrame(draw);
                        
                        // Height safety check (Taaki kabhi 0px na ho)
                        canvas.width = canvas.parentElement.clientWidth || 800;
                        canvas.height = canvas.parentElement.clientHeight || 400; 
                        
                        analyser.getByteFrequencyData(dataArray);
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        
                        // 🛡️ THE HYBRID CORS-BYPASS LOGIC
                        let sum = 0;
                        for(let i=0; i<bufferLength; i++) sum += dataArray[i];
                        
                        // Agar browser ne CORS ki wajah se audio data block kar diya hai, toh simulate karo (Like YT)
                        let isSimulated = false;
                        if (sum === 0 && !media.paused) {
                            isSimulated = true;
                        }

                        const barWidth = (canvas.width / bufferLength) * 1.5;
                        const centerY = canvas.height / 2;
                        let x = (canvas.width - (barWidth + 2) * bufferLength) / 2;
                        
                        for(let i = 0; i < bufferLength; i++) {
                            let barHeight = 0;
                            if (isSimulated) {
                                // 🌊 Simulated smooth bounce (CORS Bypass)
                                const randomVal = Math.random();
                                barHeight = randomVal * (canvas.height / 2.5);
                            } else {
                                // 🎵 Real Audio Frequencies
                                barHeight = (dataArray[i] / 255) * (canvas.height / 2.2);
                            }

                            ctx.fillStyle = window.currentThemeColor || dominantColor || '#bc8cff';
                            ctx.fillRect(x, centerY - barHeight, barWidth, barHeight); 
                            ctx.fillRect(x, centerY, barWidth, barHeight); 
                            x += barWidth + 2;
                        }
                    }
                    draw();
                } catch(e) { console.warn("Visualizer Fallback Active:", e); }
            };

            media.addEventListener('play', startVisualizer);
            if (!media.paused) startVisualizer();
        }

        // Subtitle Modal Functions
        function openSubModal() { document.getElementById('subModal').style.display = 'flex'; }
        function closeSubModal() { 
            document.getElementById('subModal').style.display = 'none'; 
            pendingSubFile = null; 
            document.getElementById('selectedFileName').innerText = ''; 
            document.getElementById('subLang').value = '';
        }
        function fileSelected(input) {
            if(input.files.length > 0) {
                pendingSubFile = input.files[0];
                document.getElementById('selectedFileName').innerText = `Selected: ${pendingSubFile.name}`;
            }
        }
        
        async function submitSubtitle() {
            if(!pendingSubFile || !activeSlug) {
                alert("Please select a file and ensure media is loaded.");
                return;
            }
            const language = document.getElementById('subLang').value.trim() || 'English';
            const formData = new FormData();
            formData.append('file', pendingSubFile);
            formData.append('media_slug', activeSlug);
            formData.append('language', language);
            try {
                const res = await fetch('/api/subtitle/upload', { method: 'POST', body: formData });
                if(res.ok) {
                    alert(`Subtitle (${language}) uploaded successfully!`);
                    closeSubModal();
                    renderWatchPage(activeSlug);
                } else alert('Failed to upload subtitle.');
            } catch(e) { console.error('Subtitle upload error:', e); alert('Error uploading subtitle.'); }
        }

        // Hybrid Recommendations Engine
        function renderHybridRelated(queryText) {
            const container = document.getElementById('relatedVideos');
            container.innerHTML = '';
            
            const currentWords = queryText.toLowerCase().split(/[\s_\-\.]+/).filter(w => w.length > 2);
            let scoredList = masterLibrary.map(f => {
                if(f.slug === activeSlug || f.slug === (ytIdActive ? null : activeSlug)) return {file: f, score: -1};
                let score = 0;
                const titleWords = f.title.toLowerCase().split(/[\s_\-\.]+/);
                titleWords.forEach(w => { if(currentWords.includes(w)) score++; });
                return {file: f, score: score};
            });
            
            scoredList.sort((a,b) => b.score - a.score || new Date(b.file.uploaded_at) - new Date(a.file.uploaded_at));
            
            scoredList.slice(0, 6).forEach(item => {
                if(item.score === -1) return;
                const f = item.file;
                const card = document.createElement('a');
                card.href = `/video?q=${f.slug}`; 
                card.className = 'related-card';
                card.onclick = (e) => { e.preventDefault(); window.history.pushState({}, '', `/video?q=${f.slug}`); routeHandler(); };
                card.innerHTML = `
                    <div class="thumb-wrapper">
                        <img src="${f.thumbnail || FALLBACK_THUMB}" class="thumb-img" onerror="this.src='${FALLBACK_THUMB}'">
                        <div class="type-badge" style="font-size:10px; padding:2px;">${getMediaType(f.mime_type)}</div>
                    </div>
                    <div class="related-info">
                        <div class="related-title">${f.title}</div>
                        <span style="font-size:11px; color:var(--yt-muted);">Vault</span>
                    </div>
                `;
                container.appendChild(card);
            });

            if(queryText.length > 3 && !ytIdActive) {
                const script = document.createElement('script');
                window.ytSuggestCallback = function(data) {
                    if(data && data[1]) {
                        data[1].slice(0, 4).forEach(suggestion => {
                            const sc = document.createElement('a');
                            sc.className = 'related-card'; 
                            sc.href = "#"; sc.style.cursor = 'pointer';
                            sc.onclick = (e) => { e.preventDefault(); document.getElementById('searchInput').value = suggestion[0]; handleSearch(); };
                            sc.innerHTML = `
                                <div class="thumb-wrapper" style="background:linear-gradient(135deg, #1a1a1a, #333); display:flex; align-items:center; justify-content:center; font-size:24px; border: 1px solid #ff0000;">🔍</div>
                                <div class="related-info"><div class="related-title" style="text-transform:capitalize;">${suggestion[0]}</div><div class="yt-pill">YouTube</div></div>
                            `;
                            container.appendChild(sc);
                        });
                    }
                };
                script.src = `https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q=${encodeURIComponent(queryText)}&callback=ytSuggestCallback`;
                script.onerror = () => console.log("YT suggestions unavailable");
                document.body.appendChild(script);
            }
        }

        function toggleTheater() { 
            document.getElementById('watchView').classList.toggle('theater-mode'); 
            window.scrollTo({top: 0, behavior: 'smooth'}); 
        }
        
        async function togglePiP() {
            const video = document.getElementById('mainMedia');
            if(!video || video.tagName !== 'VIDEO') return showActionIcon('🔲 PiP not available');
            try {
                if (document.pictureInPictureElement) { await document.exitPictureInPicture(); showActionIcon('🔲 PiP Disabled'); } 
                else { await video.requestPictureInPicture(); showActionIcon('🔲 PiP Enabled'); }
            } catch(e) { console.error('PiP error:', e); showActionIcon('🔲 PiP Error'); }
        }

        async function generateShareLink() {
            try {
                const res = await fetch('/api/share/generate', {method: 'POST'});
                if(res.ok) {
                    const data = await res.json();
                    const shareUrl = window.location.origin + window.location.pathname + `?token=${data.share_token}`;
                    navigator.clipboard.writeText(shareUrl);
                    showActionIcon('🔗 Share link copied!');
                } else alert('Failed to generate share link.');
            } catch(e) { console.error('Share error:', e); alert('Error generating share link.'); }
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

# ==========================================
# 12. ENTERPRISE MEDIA OPTIMIZER (BACKGROUND CRON)
# ==========================================
def get_optimizer_db():
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename="optimized_media.json", repo_type="dataset", token=HF_TOKEN)
        with open(file_path, "r") as f: 
            return json.load(f)
    except Exception:
        return {"optimized_slugs": []}

def save_optimizer_db(db_data):
    with open("optimized_media.json", "w") as f: 
        json.dump(db_data, f, indent=4)
    api.upload_file(
        path_or_fileobj="optimized_media.json", 
        path_in_repo="optimized_media.json", 
        repo_id=DATASET_REPO, 
        repo_type="dataset"
    )

async def media_optimizer_loop():
    logger.info("Media Optimizer Loop Initiated. Waiting 5 mins before first scan to allow server stabilization...")
    await asyncio.sleep(300)  # Boot hone ke 5 minute baad pehla scan (reduced from 15m since you have bot.py)
    
    while True:
        logger.info("Starting Background Media Scan for Unoptimized Audio...")
        try:
            main_db = get_db()
            opt_db = get_optimizer_db()
            
            all_files = main_db.get("files", [])
            optimized_slugs = opt_db.get("optimized_slugs", [])
            
            current_file_slugs = [f["slug"] for f in all_files]
            
            # STEP 1: CLEANUP (Remove deleted files from optimized history)
            new_optimized_slugs = [slug for slug in optimized_slugs if slug in current_file_slugs]
            if len(new_optimized_slugs) != len(optimized_slugs):
                opt_db["optimized_slugs"] = new_optimized_slugs
                save_optimizer_db(opt_db)
                logger.info("Cleaned up deleted files from optimized history.")

            # STEP 2: SCAN & FIX
            for f in all_files:
                # Target only videos that are NOT external and NOT yet optimized
                if f.get("mime_type", "").startswith("video/") and not f.get("is_external") and f["slug"] not in new_optimized_slugs:
                    slug = f["slug"]
                    repo_path = f["path"]
                    logger.info(f"Optimizing Media (Converting Audio to AAC): {slug}")
                    
                    try:
                        # 1. Download file from HF to /tmp/
                        local_path = hf_hub_download(repo_id=DATASET_REPO, filename=repo_path, repo_type="dataset", token=HF_TOKEN)
                        temp_out = f"/tmp/fixed_{slug}.mp4"
                        
                        # 2. Run FFmpeg (Video copy, Audio convert to AAC)
                        cmd = ["ffmpeg", "-y", "-i", local_path, "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", temp_out]
                        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        await process.communicate()
                        
                        if os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                            # 3. Upload fixed file back to HF (Overwrite the original)
                            await asyncio.to_thread(
                                api.upload_file, 
                                path_or_fileobj=temp_out, 
                                path_in_repo=repo_path, 
                                repo_id=DATASET_REPO, 
                                repo_type="dataset"
                            )
                            
                            # 4. Mark as completed in JSON
                            opt_db["optimized_slugs"].append(slug)
                            save_optimizer_db(opt_db)
                            new_optimized_slugs.append(slug)
                            logger.info(f"Successfully Optimized & Synced: {slug}")
                            
                            # Cleanup temp output
                            os.remove(temp_out)
                        
                        # Cleanup downloaded original
                        if os.path.exists(local_path):
                            os.remove(local_path)
                            
                    except Exception as e:
                        logger.error(f"Failed to optimize {slug}: {e}")
                        
        except Exception as e:
            logger.error(f"Optimizer Loop Error: {e}")
            
        logger.info("Media scan complete. Sleeping for 24 hours.")
        await asyncio.sleep(86400)  # 24 Hours sleep cycle

# ==========================================
# 13. OMNISCIENT TELEGRAM BOT (MAX POWER MTPROTO - PYROGRAM)
# ==========================================
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import difflib
import subprocess
import mimetypes
import os
import uuid
import time
import json
import asyncio
import math
from datetime import datetime

# Fetch ENV Variables
TG_API_ID = int(os.environ.get("TG_API_ID", "0"))
TG_API_HASH = os.environ.get("TG_API_HASH", "dummy")
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "dummy")
TG_SESSION_STRING = os.environ.get("TG_SESSION_STRING", "") # For True 2GB UserBot Power

# Fixed Domain
STATIC_DOMAIN = "https://static.qlynk.me"

# Initialize Pyrogram MTProto Client
# Initialize Pyrogram MTProto Client
if TG_SESSION_STRING:
    tg_app = Client(
        "qlynk_userbot",
        session_string=TG_SESSION_STRING,
        api_id=TG_API_ID,
        api_hash=TG_API_HASH
    )
else:
    tg_app = Client(
        "qlynk_bot",
        api_id=TG_API_ID,
        api_hash=TG_API_HASH,
        bot_token=TG_BOT_TOKEN
    )

# --- GLOBAL QUEUE LOCK (Ek ek karke upload karne ke liye) ---
upload_lock = asyncio.Lock()

# --- Telegram Auth DB Helpers ---
def get_tg_auth_db():
    try:
        path = hf_hub_download(repo_id=DATASET_REPO, filename="tg_users.json", repo_type="dataset", token=HF_TOKEN)
        with open(path, "r") as f: return json.load(f)
    except Exception: return {"authorized_users": []}

def save_tg_auth_db(db):
    with open("tg_users.json", "w") as f: json.dump(db, f, indent=4)
    api.upload_file(path_or_fileobj="tg_users.json", path_in_repo="tg_users.json", repo_id=DATASET_REPO, repo_type="dataset")

def get_channel_db():
    try:
        path = hf_hub_download(repo_id=DATASET_REPO, filename="channel_db.json", repo_type="dataset", token=HF_TOKEN)
        with open(path, "r") as f: return json.load(f)
    except Exception: return {"messages": []}

def save_channel_db(db):
    with open("channel_db.json", "w") as f: json.dump(db, f, indent=4)
    api.upload_file(path_or_fileobj="channel_db.json", path_in_repo="channel_db.json", repo_id=DATASET_REPO, repo_type="dataset")    

def is_auth(user_id: int):
    db = get_tg_auth_db()
    return user_id in db.get("authorized_users", [])

def check_target_chat(message):
    if TG_SESSION_STRING:
        return message.chat.id == message.from_user.id
    return True

# --- COMMAND: /start ---
@tg_app.on_message(filters.command("start"))
async def start_cmd(client, message):
    # DHYAN DE: Yahan se 'check_target_chat' wali line hata di gayi hai
    # Taki sabko tera branding message aur buttons dikhein!
    
    keyboard = [
        [InlineKeyboardButton("💻 Source Code", url="https://huggingface.co/spaces/deydeep/static-files/")],
        [InlineKeyboardButton("🐙 GitHub Profile", url="https://github.com/deepdeyiitgn"),
         InlineKeyboardButton("👨‍💻 About Deep", url="https://clock.qlynk.me/about-deep")],
        [InlineKeyboardButton("📸 Instagram", url="https://www.instagram.com/deepdey.official/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 **Welcome to Qlynk Node Master!**\n\n"
        "I am the advanced remote control for your secure file hosting datacenter engineered by **Deep Dey**.\n\n"
        "To unlock my full potential (Uploads, Auto-Search, Batch Uploads), please verify your identity using:\n"
        "👉 `/verify`\n\n"
        "🎧 **Need Help or waiting for a Premium Receipt?**\n"
        "Type 👉 `/support`"
    )
    await message.reply_text(welcome_text, reply_markup=reply_markup, disable_web_page_preview=True)

# --- COMMAND: /verify ---
@tg_app.on_message(filters.command("verify"))
async def verify_cmd(client, message):
    if not check_target_chat(message): return
    if is_auth(message.from_user.id):
        await message.reply_text("✅ You are the Owner and already verified!\n\nYou can now upload files, search the database, or use /batch.")
    else:
        await message.reply_text("🔐 **System Locked.**\n\nPlease enter your `SPACE_PASSWORD` below to mount the storage node and verify your identity.")

# --- COMMAND: /logout ---
@tg_app.on_message(filters.command("logout"))
async def logout_cmd(client, message):
    if not check_target_chat(message): return
    if not is_auth(message.from_user.id):
        await message.reply_text("You are not logged in.")
        return
        
    db = get_tg_auth_db()
    auth_list = db.get("authorized_users", [])
    if message.from_user.id in auth_list:
        auth_list.remove(message.from_user.id)
        db["authorized_users"] = auth_list
        save_tg_auth_db(db)
        await message.reply_text("🚪 Logged out successfully. Datacenter unmounted.")

# --- COMMAND: /batch ---
batch_users = {} 
@tg_app.on_message(filters.command("batch"))
async def batch_cmd(client, message):
    if not check_target_chat(message): return
    if not is_auth(message.from_user.id): 
        await message.reply_text("🚫 Please /verify first.")
        return
    
    user_id = message.from_user.id
    if batch_users.get(user_id):
        batch_users[user_id] = False
        await message.reply_text("📦 **Batch Mode Deactivated.**\nOperating in standard single-file mode.")
    else:
        batch_users[user_id] = True
        await message.reply_text("📦 **Batch Mode Active.**\n\nYou can now forward or send multiple files. The system will strictly queue and process them one-by-one to protect server disk space.")

# --- COMMAND: /connect ---
@tg_app.on_message(filters.command("connect"))
async def connect_cmd(client, message):
    if not check_target_chat(message): return
    if not is_auth(message.from_user.id):
        await message.reply_text("🚫 Please /verify first to use this command.")
        return

    if len(message.command) < 2:
        await message.reply_text("⚠️ Syntax: `/connect [channel_or_group_id]`\nExample: `/connect -100123456789`")
        return

    try:
        target_chat = int(message.command[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid ID format. Must be a number (usually starting with -100).")
        return

    try:
        member = await client.get_chat_member(target_chat, client.me.id)
        if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await message.reply_text("❌ Bot is in the chat but does NOT have Admin permissions. Please make it an admin first.")
            return

        db = get_tg_auth_db()
        db["connected_chat"] = target_chat
        save_tg_auth_db(db)
        
        chat_info = await client.get_chat(target_chat)

        # 💾 THE MAGIC: Save the session file to Hugging Face so it NEVER forgets
        try:
            session_file = "qlynk_userbot.session" if os.environ.get("TG_SESSION_STRING") else "qlynk_bot.session"
            if os.path.exists(session_file):
                api.upload_file(path_or_fileobj=session_file, path_in_repo=session_file, repo_id=DATASET_REPO, repo_type="dataset")
        except Exception as e:
            logger.warning(f"Session sync failed: {e}")

        await message.reply_text(f"✅ **Successfully Connected!**\n\nBot is now linked to: **{chat_info.title}**\n💾 Memory synced to Datacenter. I won't forget this channel again!")

    except Exception as e:
        await message.reply_text(f"❌ **Could not connect.**\n\nMake sure the bot is added to the channel as **Admin**.\n\n*(💡 Pro Tip: Since memory was just wiped, Forward any one message from that channel to me here so my memory can register its ID, then try /connect again!)*\n\nError Details: `{e}`")
        
# --- COMMAND: /index (DEEP SCAN BYPASS) ---
@tg_app.on_message(filters.command("index"))
async def index_cmd(client, message):
    if not check_target_chat(message): return
    if not is_auth(message.from_user.id):
        await message.reply_text("🚫 Please /verify first.")
        return

    tg_db = get_tg_auth_db()
    connected_chat = tg_db.get("connected_chat")

    if not connected_chat:
        await message.reply_text("❌ No channel connected. Use `/connect [id]` first.")
        return

    status_msg = await message.reply_text("🔄 **Initializing Deep Scan Bypass...**\nCalculating channel depth. Please wait...")

    db = {"messages": []}
    count = 0

    try:
        # 1. Sabse pehle latest message ki ID nikalte hain taaki pata chale kahan tak scan karna hai
        dummy = await client.send_message(connected_chat, "Initializing Datacenter Scan...")
        latest_id = dummy.id
        await dummy.delete()

        # 2. Telegram Bot limit: Hum ek baar mein max 200 messages fetch kar sakte hain
        BATCH_SIZE = 200
        
        for start_id in range(1, latest_id + 1, BATCH_SIZE):
            end_id = min(start_id + BATCH_SIZE, latest_id + 1)
            msg_ids = list(range(start_id, end_id))
            
            try:
                # get_messages is allowed for bots! Hum exact ID bhej kar data nikal lenge
                messages = await client.get_messages(chat_id=connected_chat, message_ids=msg_ids)
                
                for msg in messages:
                    # Agar message delete ho chuka hai ya empty hai toh ignore karo
                    if getattr(msg, 'empty', False) or msg is None: 
                        continue
                        
                    media = getattr(msg, 'video', None) or getattr(msg, 'document', None) or getattr(msg, 'audio', None)
                    if media:
                        # Caption ya File Name nikalna (Pehle wali logic)
                        title = getattr(msg, 'caption', None)
                        if not title:
                            title = getattr(media, 'file_name', f"Media_{msg.id}")
                            
                        if title:
                            # Clean the title (sirf pehli line)
                            title = str(title).split('\n')[0].strip()
                            db["messages"].append({
                                "id": msg.id,
                                "title": title
                            })
                            count += 1
                            
            except Exception as batch_err:
                logger.warning(f"Batch {start_id} failed: {batch_err}")
                await asyncio.sleep(2) # Error aane par server ko thoda aaram dena zaroori hai
                
            # Har 1000 messages ke baad status update (Telegram API Flood Wait se bachne ke liye)
            if start_id % 1000 == 1:
                await status_msg.edit_text(f"🔄 **Deep Indexing in Progress...**\nScanning Message ID: **{start_id}** of **{latest_id}**\nFound **{count}** media files so far...\n\n*(Do not send any other commands while this is running)*")
                await asyncio.sleep(1.5) # Anti-Flood Wait

        # 3. Jab pura scan ho jaye, HF Database me hamesha ke liye save kar do
        save_channel_db(db)
        await status_msg.edit_text(f"✅ **Deep Indexing Complete!**\n\nSuccessfully bypassed bot limits and mapped **{count}** media files to the Datacenter Database.\n\nSmart Search is now fully operational! 🎉")

    except Exception as e:
        await status_msg.edit_text(f"❌ Indexing Failed.\nError: `{e}`")

# --- HELPER: Auto-Search Pagination Builder (SMART ENGINE) ---
async def send_search_page(client, message, query, page=0, is_callback=False):
    # 🌟 TEXT NORMALIZER: Replace dots, hyphens, underscores with spaces & lowercase
    def clean_text(t):
        return re.sub(r'[\.\_\-]', ' ', str(t)).lower().strip()

    clean_query = clean_text(query)
    all_results = []

    # 1. Fetch from HF Vault
    db = get_db()
    files = [f for f in db.get("files", []) if not f.get("is_external") and f.get("mime_type", "").startswith(("video/", "audio/"))]
    
    vault_map = {}
    for f in files:
        orig_title = f.get("title", f.get("filename", ""))
        vault_map[clean_text(orig_title)] = (f["slug"], orig_title)
        
    vault_matches = difflib.get_close_matches(clean_query, list(vault_map.keys()), n=30, cutoff=0.3)
    for match in vault_matches:
        slug, orig_title = vault_map[match]
        all_results.append(("vault", slug, f"📁 [Vault] {orig_title}"))

    # 2. Fetch from Connected Channel Index (JSON Database)
    tg_db = get_tg_auth_db()
    connected_chat = tg_db.get("connected_chat")
    
    if connected_chat:
        chan_db = get_channel_db()
        chan_messages = chan_db.get("messages", [])
        
        chan_map = {}
        for m in chan_messages:
            orig_title = m["title"]
            chan_map[clean_text(orig_title)] = (m["id"], orig_title)
            
        chan_matches = difflib.get_close_matches(clean_query, list(chan_map.keys()), n=30, cutoff=0.3)
        for match in chan_matches:
            msg_id, orig_title = chan_map[match]
            all_results.append(("chan", msg_id, f"📡 [Channel] {orig_title}"))

    if not all_results:
        text_msg = "🔍 No media assets found in the Vault or Channel Index for that name."
        if is_callback: await message.edit_text(text_msg)
        else: await message.reply_text(text_msg)
        return

    # --- Pagination Math ---
    ITEMS_PER_PAGE = 5
    total_items = len(all_results)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_results = all_results[start_idx:end_idx]
    
    keyboard = []
    for item_type, item_id, item_title in page_results:
        if item_type == "vault":
            keyboard.append([InlineKeyboardButton(item_title, callback_data=f"opt_{item_id}")])
        else:
            keyboard.append([InlineKeyboardButton(item_title, callback_data=f"chan_{item_id}")])
            
    nav_row = []
    safe_query = query[:30] 
    
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"pg_{page-1}_{safe_query}"))
        
    nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"pg_{page+1}_{safe_query}"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = f"🔍 Found **{total_items}** assets for `{query}`. (Page {page+1}/{total_pages}):"
    
    if is_callback:
        await message.edit_text(msg_text, reply_markup=reply_markup)
    else:
        await message.reply_text(msg_text, reply_markup=reply_markup)
        
# --- TEXT HANDLER: Auth & Strict Vault Auto-Search ---
@tg_app.on_message(filters.text & ~filters.command(["start", "verify", "logout", "batch", "connect", "index", "support", "close"]))
async def text_handler(client, message):
    if not check_target_chat(message): return
    
    # 🛡️ FIX: Agar message channel ki taraf se aaya hai (No user ID), toh ignore karo (Crash Bypass)
    if not message.from_user: return 
    
    text = message.text
    user_id = message.from_user.id
    
    # 1. Check Password
    if not is_auth(user_id):
        if text == SPACE_PASSWORD:
            db = get_tg_auth_db()
            auth_list = db.get("authorized_users", [])
            if user_id not in auth_list:
                auth_list.append(user_id)
                db["authorized_users"] = auth_list
                save_tg_auth_db(db)
            await message.reply_text("🔓 **Access Granted!**\n\nYou are now securely connected to the Qlynk Datacenter.\n- Send a file to upload.\n- Type a video name to search.", parse_mode=enums.ParseMode.MARKDOWN)
            try: await message.delete()
            except: pass
        else:
            await message.reply_text("❌ Incorrect Password. Intrusion attempt logged.")
        return

    # 2. Trigger Smart Paginated Search (Jo Beast.Games aur Beast Games dono ko match karega)
    await send_search_page(client, message, query=text, page=0, is_callback=False)

# --- CALLBACK QUERIES: Buttons ---
@tg_app.on_callback_query()
async def button_handler(client, query: CallbackQuery):
    data = query.data
    
    if data.startswith("opt_"):
        slug = data.split("_", 1)[1]
        
        db = get_db()
        file_record = next((f for f in db.get("files", []) if f["slug"] == slug), None)
        
        if not file_record:
            await query.answer("File not found in database.", show_alert=True)
            return

        title = file_record.get("title", "Unknown Title")
        size = format_size(file_record.get("size_bytes", 0))
        thumb_url = file_record.get("thumbnail", "")
        if thumb_url and thumb_url.startswith("/f/"):
            thumb_url = f"{STATIC_DOMAIN}{thumb_url}"
        
        keyboard = [
            [InlineKeyboardButton("🔗 Secure Stream Link", callback_data=f"link_{slug}"),
             InlineKeyboardButton("📥 Direct Download", callback_data=f"dl_{slug}")]
        ]
        
        msg_text = f"🎬 **{title}**\n\n📦 Size: {size}\n⚙️ Engine: Local Vault Asset\n\nHow do you want to receive this?"
        
        # 🛠️ THE FIX: Pehle photo bhejne ki koshish karo
        if thumb_url and thumb_url.startswith("http"):
            try:
                await client.send_photo(
                    chat_id=query.message.chat.id, 
                    photo=thumb_url, 
                    caption=msg_text, 
                    reply_markup=InlineKeyboardMarkup(keyboard), 
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                # Agar photo successfully chali gayi, tabhi purana message delete karo
                await query.message.delete()
                return
            except Exception as e:
                logger.warning(f"Photo send failed, falling back to text: {e}")
                # Agar photo fail hui, toh error suppress karke aage badho (text edit karega)
            
        try:
            # Agar photo nahi hai ya bhejne mein error aaya, toh purane message ko hi edit kar do
            await query.message.edit_text(
                text=msg_text, 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception:
            pass # Ignore MESSAGE_NOT_MODIFIED
        
    elif data.startswith("link_"):
        slug = data.split("_", 1)[1]
        url = f"{STATIC_DOMAIN}/f/{slug}"
        await query.message.edit_text(text=f"🔗 Here is your secure streaming link:\n\n{url}")
        
    elif data.startswith("dl_"):
        slug = data.split("_", 1)[1]
        db = get_db()
        file_record = next((f for f in db.get("files", []) if f["slug"] == slug), None)
        
        if file_record:
            await query.message.edit_text("📤 Downloading from HF Vault and processing Media...")
            try:
                # 1. Download Main File
                file_path = hf_hub_download(repo_id=DATASET_REPO, filename=file_record["path"], repo_type="dataset", token=HF_TOKEN)
                
                # 2. Setup Default Caption with Watermark
                caption = f"🎬 **{file_record.get('title')}**\n\n✨ By: Static.qlynk.me"
                
                # 3. Check if it's a Video for native Telegram Streaming
                if str(file_record.get("mime_type", "")).startswith("video/"):
                    watermarked_thumb = None
                    thumb_path = None
                    
                    # 4. Process Thumbnail & Add Watermark via FFmpeg
                    thumb_slug_full = file_record.get("thumbnail", "")
                    if thumb_slug_full and thumb_slug_full.startswith("/f/"):
                        t_slug = thumb_slug_full.replace("/f/", "")
                        t_record = next((f for f in db.get("files", []) if f["slug"] == t_slug), None)
                        
                        if t_record:
                            try:
                                thumb_path = hf_hub_download(repo_id=DATASET_REPO, filename=t_record["path"], repo_type="dataset", token=HF_TOKEN)
                                watermarked_thumb = f"/tmp/wm_{t_slug}.jpg"
                                
                                # PURANA CODE (Keval lines preserve karne ke liye comments me dala hai)
                                # cmd = [
                                #     "ffmpeg", "-y", "-i", thumb_path, 
                                #     "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/freefont/FreeSansBold.ttf:text='By\: Static.qlynk.me':x=(w-text_w)/2:y=h-th-15:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6",
                                #     watermarked_thumb
                                # ]
                                # process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                # await process.communicate()
                                
                                # NAYA ROBUST FFMPEG COMMAND & FALLBACK
                                cmd = [
                                    "ffmpeg", "-y", "-i", thumb_path, 
                                    "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/freefont/FreeSansBold.ttf:text='By\: Static.qlynk.me':x=(w-text_w)/2:y=h-th-15:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6",
                                    watermarked_thumb
                                ]
                                process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                await process.communicate()
                                
                                # 🛡️ FIX: Agar watermark lagne ke baad file choti (0 bytes) ho ya bani hi na ho
                                if not os.path.exists(watermarked_thumb) or os.path.getsize(watermarked_thumb) < 1024:
                                    logger.warning("FFmpeg generated black/corrupt thumb. Reverting to Original.")
                                    watermarked_thumb = thumb_path # Fallback to original thumb
                            except Exception as e:
                                logger.warning(f"Thumbnail Watermark failed: {e}")
                                watermarked_thumb = thumb_path # Hard fallback

                    # 5. Send as Native Streamable Video
                    # 🛡️ FIX: 'thumb' argument ko force karte hain original ya watermarked photo se
                    final_thumb_to_send = watermarked_thumb if (watermarked_thumb and os.path.exists(watermarked_thumb)) else thumb_path
                    
                    await client.send_video(
                        chat_id=query.message.chat.id, 
                        video=file_path, 
                        thumb=final_thumb_to_send, # Yahan black screen avoid ho jayega
                        caption=caption,
                        file_name=file_record["filename"],
                        supports_streaming=True
                    )
                    
                    # 6. Cleanup Temp Watermarked Thumb
                    if watermarked_thumb and watermarked_thumb != thumb_path and os.path.exists(watermarked_thumb):
                        os.remove(watermarked_thumb)
                        
                else:
                    # 7. Fallback for PDF, Zip, Audio etc. (Send as Document)
                    await client.send_document(
                        chat_id=query.message.chat.id, 
                        document=file_path, 
                        file_name=file_record["filename"], 
                        caption=caption
                    )
                
                await query.message.delete()
                
            except Exception as e:
                url = f"{STATIC_DOMAIN}/f/{slug}"
                await query.message.edit_text(f"⚠️ **Telegram Server Size Limit!**\n\n🔗 Please use your secure Vault link:\n{url}")

    elif data.startswith("chan_"):
        msg_id = int(data.split("_", 1)[1])
        tg_db = get_tg_auth_db()
        connected_chat = tg_db.get("connected_chat")
        
        if not connected_chat:
            await query.answer("Channel connection lost.", show_alert=True)
            return
            
        await query.message.edit_text("📤 Extracting directly from Channel...")
        try:
            # 1. Pehle Original message ki details nikal lo
            orig_msg = await client.get_messages(connected_chat, msg_id)
            media = getattr(orig_msg, 'video', None) or getattr(orig_msg, 'document', None) or getattr(orig_msg, 'audio', None)
            
            title = getattr(orig_msg, 'caption', None)
            if not title and media:
                title = getattr(media, 'file_name', "Channel Media")
            
            title = str(title).split('\n')[0].strip() if title else "Media Asset"
            
            # 2. Naya Watermarked Caption banao
            new_caption = f"🎬 **{title}**\n\n✨ By: Static.qlynk.me"

            # 3. Message copy karo (bina forward tag ke) aur Naya caption lagao!
            await client.copy_message(
                chat_id=query.message.chat.id,
                from_chat_id=connected_chat,
                message_id=msg_id,
                caption=new_caption # 👈 Caption Watermark lag gaya!
            )
            await query.message.delete()
        except Exception as e:
            await query.message.edit_text(f"❌ Failed to fetch from channel.\nError: {e}")

    elif data.startswith("pg_"):
        parts = data.split("_", 2)
        page = int(parts[1])
        search_q = parts[2]
        # Edit the current message with the new page
        await send_search_page(client, query.message, query=search_q, page=page, is_callback=True)
        
    elif data == "ignore":
        # Do nothing (used for the 'Page X/Y' indicator button)
        await query.answer()        
            
# --- MEDIA HANDLER: Smart Uploads, Queue System, MKV Fix & Native Thumbnails ---
@tg_app.on_message(filters.media | filters.document)
async def media_handler(client, message):
    if not check_target_chat(message): return
    if not is_auth(message.from_user.id): 
        await message.reply_text("🚫 Please /verify first.")
        return
    
    # Send waiting message immediately
    msg = await message.reply_text("⏳ **File Received!**\nAdded to the processing queue. Please wait for your turn...", parse_mode=enums.ParseMode.MARKDOWN)
    
    # 🔒 QUEUE SYSTEM: Yeh ensure karega ki ek time par ek hi file process ho
    async with upload_lock:
        await msg.edit_text("🔄 **Your turn!** Initializing Datacenter Upload Sequence...", parse_mode=enums.ParseMode.MARKDOWN)
        
        media = message.document or message.video or message.audio
        if not media and message.photo: media = message.photo
            
        if not media:
            await msg.edit_text("❌ Unknown media format.")
            return

        filename = getattr(media, 'file_name', f"telegram_upload_{uuid.uuid4().hex[:5]}")
        
        # 🎵 FIX: Clean Title Logic (Remove extension and replace underscores with spaces)
        if message.caption:
            title = message.caption
        else:
            # os.path.splitext filename ko split karta hai: ('My_Awesome_Song', '.mp3')
            # Hum sirf pehla part [0] lenge aur '_' ko ' ' (space) se replace kar denge
            title = os.path.splitext(filename)[0].replace("_", " ")
            
        slug = uuid.uuid4().hex  # <--- YAHAN CHANGE KIYA HAI
        ext = os.path.splitext(filename)[1].lower() if "." in filename else ".bin"
        temp_path = f"/tmp/raw_{slug}{ext}"
        final_path = temp_path
        
        start_time = time.time()
        last_update_time = start_time
        
        async def dl_progress(current, total):
            nonlocal last_update_time
            now = time.time()
            if now - last_update_time > 1.5: 
                percent = (current / total) * 100
                time_elapsed = now - start_time
                speed = current / time_elapsed if time_elapsed > 0 else 0
                eta = (total - current) / speed if speed > 0 else 0
                try:
                    await msg.edit_text(f"📥 **Downloading from Telegram...**\n\nProgress: {percent:.1f}%\nSpeed: {(speed/1024/1024):.2f} MB/s\nETA: {int(eta)}s\n[{format_size(current)} / {format_size(total)}]", parse_mode=enums.ParseMode.MARKDOWN)
                    last_update_time = now
                except: pass

        try:
            db = get_db()
            files_list = db.setdefault("files", [])
            upload_timestamp = datetime.utcnow().isoformat() + "Z"
            final_thumbnail_url = ""

            # 1. Native Telegram Thumbnail Extraction (CPU Friendly & Fast)
            if getattr(media, 'thumbs', None) and len(media.thumbs) > 0:
                await msg.edit_text("🖼️ Extracting Native Telegram Thumbnail...")
                thumb_file_id = media.thumbs[0].file_id
                thumb_temp = f"/tmp/thumb_{slug}.jpg"
                
                downloaded_thumb = await client.download_media(thumb_file_id, file_name=thumb_temp)
                
                if downloaded_thumb and os.path.exists(downloaded_thumb):

                    # 🛠️ NAYA FIX: File delete hone se pehle uska asli size bytes mein nikal liya
                    thumb_size = os.path.getsize(thumb_temp)
                    
                    thumb_repo_path = f"files/thumb_{slug}.jpg"
                    await asyncio.to_thread(api.upload_file, path_or_fileobj=thumb_temp, path_in_repo=thumb_repo_path, repo_id=DATASET_REPO, repo_type="dataset")
                   # 🛡️ FIX: Slug aur URL mein se '.jpg' extension permanently hata diya
                    final_thumbnail_url = f"/f/thumb_{slug}"
                    os.remove(thumb_temp)

                    # Add thumbnail record to DB
                    files_list.append({
                    "slug": f"thumb_{slug}",  # 🛡️ FIX: Sirf plain text, NO EXTENSION!
                    "filename": f"thumbnail_{slug}.jpg",  # Asli file name intact rahega
                    "path": thumb_repo_path,
                    "title": "Native Telegram Thumbnail", 
                    "thumbnail": f"/f/thumb_{slug}", # 🛡️ FIX: Yahan blank ki jagah khud ka slug link daal diya!
                    "mime_type": "image/jpeg",
                    "size_bytes": thumb_size,  # 🛡️ FIX: Ab 0 ki jagah actual image size aayega!
                    "uploaded_at": upload_timestamp,
                    "is_external": False,
                    "external_url": ""
                })
                    
            # 2. Download Main File Fast via MTProto
            await message.download(file_name=temp_path, progress=dl_progress)
            await msg.edit_text("✅ File Cached Locally.\n\n🔍 Analyzing File Structure...")
            
            mime_type, _ = mimetypes.guess_type(temp_path)
            if not mime_type: mime_type = "application/octet-stream"

            # 3. MKV / Unsupported Video Optimizer (MP4/AAC Force Convert)
            is_video = mime_type.startswith("video/") or ext in ['.mkv', '.avi', '.mov', '.flv', '.wmv']
            
            if is_video and ext != '.mp4':
                await msg.edit_text("🛠️ Optimizing Video Engine (MKV to MP4 & AAC Audio Fix)...\nThis may take a few minutes for heavy files.")
                final_path = f"/tmp/fixed_{slug}.mp4"
                filename = os.path.splitext(filename)[0] + ".mp4"
                mime_type = "video/mp4"
                
                cmd = ["ffmpeg", "-y", "-i", temp_path, "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", final_path]
                process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                await process.communicate()
                
                if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                    os.remove(temp_path) 
                else:
                    final_path = temp_path 
            
            # 4. Final Sync to Hugging Face
            await msg.edit_text("🔄 Syncing Optimized Media to HF Datacenter... (Please Wait)")
            
            repo_path = f"files/{slug}_{filename}"
            file_size_disk = os.path.getsize(final_path)

            await asyncio.to_thread(
                api.upload_file, path_or_fileobj=final_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset"
            )
            os.remove(final_path)
            
            # 🛡️ FIX: Agar uploaded file WebP/SVG/GIF/Image hai, toh woh khud apna thumbnail banegi
            if not final_thumbnail_url and mime_type and mime_type.startswith("image/"):
                final_thumbnail_url = f"/f/{slug}"
            
            # 5. Update Main DB Record
            file_record = {
                "slug": slug,
                "filename": filename,
                "path": repo_path,
                "title": title,
                "thumbnail": final_thumbnail_url,
                "mime_type": mime_type,
                "size_bytes": file_size_disk,
                "uploaded_at": upload_timestamp,
                "is_external": False,
                "external_url": ""
            }
            files_list.append(file_record)
            save_db(db)
            
            url = f"{STATIC_DOMAIN}/f/{slug}"
            batch_status = "(Batch Queue Active)" if batch_users.get(message.from_user.id) else ""
            await msg.edit_text(f"🎉 **Upload Complete!** {batch_status}\n\n**File:** {title}\n**Size:** {format_size(file_size_disk)}\n\n**Secure Link:**\n{url}", parse_mode=enums.ParseMode.MARKDOWN)
            
        except Exception as e:
            await msg.edit_text(f"❌ Upload Failed (Telegram Server Limits or Engine Crash): {e}")
            # Ensure cleanup if crashed
            if os.path.exists(temp_path): os.remove(temp_path)
            if final_path != temp_path and os.path.exists(final_path): os.remove(final_path)

# ==========================================
# 14. QLYNK SaaS CHECKOUT & PAYMENT ENGINE (ENTERPRISE EDITION)
# ==========================================
import razorpay
from fpdf import FPDF
import re
import httpx
from collections import defaultdict
import time

# --- Premium Pricing Plans ---
PLANS = {
    "basic": {"name": "Basic", "price_inr": 49, "days": 1, "desc": "24 Hours Full Access"},
    "pro": {"name": "Pro", "price_inr": 99, "days": 3, "desc": "3 Days Unlimited Access"},
    "ultra": {"name": "Ultra", "price_inr": 299, "days": 7, "desc": "7 Days Premium Access"}
}

# --- Razorpay Setup & Feature Toggle ---
CHECKOUT_TOGGLE = os.environ.get("CHECKOUT_TOGGLE")
RZP_KEY = os.environ.get("RAZORPAY_KEY_ID")

def is_checkout_enabled():
    # Check if toggle exists and matches the SPACE_PASSWORD
    return CHECKOUT_TOGGLE and SPACE_PASSWORD and CHECKOUT_TOGGLE == SPACE_PASSWORD
RZP_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
rzp_client = razorpay.Client(auth=(RZP_KEY, RZP_SECRET)) if RZP_KEY and RZP_SECRET else None

# --- Advanced Security: Anti-Spam Rate Limiter ---
# Prevents hackers from spamming fake order creation requests
rate_limiter_db = defaultdict(list)

def check_rate_limit(ip: str):
    now = time.time()
    # Remove old requests (older than 1 minute)
    rate_limiter_db[ip] = [t for t in rate_limiter_db[ip] if now - t < 60]
    if len(rate_limiter_db[ip]) > 5: # Max 5 order attempts per minute
        return False
    rate_limiter_db[ip].append(now)
    return True

# --- PDF Generator Helper with SVG Logo ---
def generate_receipt_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Fetch & Embed Logo
    logo_path = "/tmp/qlynk_logo_receipt.svg"
    try:
        if not os.path.exists(logo_path):
            with httpx.Client() as client:
                r = client.get("https://qlynk.vercel.app/quicklink-logo.svg", timeout=10)
                if r.status_code == 200:
                    with open(logo_path, "wb") as f:
                        f.write(r.content)
        # Add logo to PDF (fpdf2 supports basic SVGs)
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=10, y=8, w=25)
    except Exception as e:
        logger.warning(f"Failed to embed PDF logo: {e}")

    # 2. Header
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, txt="QLYNK HOST - SECURE RECEIPT", ln=True, align='R')
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, txt="Official Datacenter Node Invoice", ln=True, align='R')
    
    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)
    
    # 3. Transaction Meta
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 8, txt=f"Order ID: {data['order_id']}")
    pdf.cell(90, 8, txt=f"Date: {data['date'][:10]}", align='R', ln=True)
    pdf.cell(100, 8, txt=f"Status: {data['status'].upper()}")
    pdf.cell(90, 8, txt=f"Method: Razorpay Gateway", align='R', ln=True)
    
    # 4. Data Tables
    pdf.ln(10)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="  Billed To:", ln=True, fill=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, txt=f"  Name: {data['name']}", ln=True)
    pdf.cell(0, 8, txt=f"  Email: {data['email']}", ln=True)
    pdf.cell(0, 8, txt=f"  Contact: {data['tg_contact']}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="  Purchase Summary:", ln=True, fill=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, txt=f"  Qlynk {data['plan_name']} Plan Access")
    pdf.cell(90, 8, txt=f"INR {data['amount']}.00", align='R', ln=True)
    
    # 5. Token Box (If Success)
    if data['status'] == 'success':
        pdf.ln(15)
        pdf.set_fill_color(230, 255, 230)
        pdf.set_draw_color(46, 160, 67)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="  YOUR SECURE ACCESS TOKEN", ln=True, border='LRT', fill=True)
        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 12, txt=f"  {data['token']}", ln=True, border='LRB')
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 8, txt=f"  Valid Until: {data['expires_at']}", ln=True)
        
    # 6. Footer
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(120, 120, 120)
    note = "Thank you for using Qlynk! This is an auto-generated secure receipt." if data['status'] == 'success' else f"Transaction Aborted. Reason: {data.get('reason', 'User Cancelled')}"
    pdf.cell(0, 10, txt=note, ln=True, align='C')
    
    temp_pdf_path = f"/tmp/receipt_{data['order_id']}.pdf"
    pdf.output(temp_pdf_path)
    return temp_pdf_path

# --- Database User Handlers ---
def get_user_db(email_slug):
    try:
        path = hf_hub_download(repo_id=DATASET_REPO, filename=f"users/{email_slug}/profile.json", repo_type="dataset", token=HF_TOKEN)
        with open(path, "r") as f: return json.load(f)
    except: return {"profile": {}, "history": []}

def save_user_db(email_slug, db):
    path = f"users/{email_slug}/profile.json"
    with open("/tmp/temp_profile.json", "w") as f: json.dump(db, f, indent=4)
    api.upload_file(path_or_fileobj="/tmp/temp_profile.json", path_in_repo=path, repo_id=DATASET_REPO, repo_type="dataset")

# --- Telegram Notifier ---
async def send_tg_receipt(tg_contact, text, pdf_path=None):
    try:
        if TG_API_ID != 0 and TG_BOT_TOKEN != "dummy":
            if pdf_path: await tg_app.send_document(tg_contact, document=pdf_path, caption=text)
            else: await tg_app.send_message(tg_contact, text)
    except Exception as e:
        logger.warning(f"Failed to send TG Notification to {tg_contact}: {e}")

# --- Massive Premium Frontend HTML Payload ---
CHECKOUT_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qlynk Host - Secure Checkout</title>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        :root { --bg: #050505; --card: rgba(22, 27, 34, 0.6); --accent: #bc8cff; --accent-glow: rgba(188, 140, 255, 0.4); --text: #e1e4e8; --border: #30363d; --success: #2ea043; --danger: #da3633; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 20px; background-image: radial-gradient(circle at top, #1a1a2e 0%, transparent 40%); min-height: 100vh; overflow-x: hidden;}
        
        /* Custom Toast Notifications */
        #toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
        .toast { background: #1f2428; border: 1px solid var(--border); color: #fff; padding: 15px 20px; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 10px; transform: translateX(120%); transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55); }
        .toast.show { transform: translateX(0); }
        .toast.success { border-left: 4px solid var(--success); }
        .toast.error { border-left: 4px solid var(--danger); }

        .navbar { display: flex; justify-content: space-between; align-items: center; padding: 15px 0; border-bottom: 1px solid var(--border); margin-bottom: 40px; }
        .nav-brand { display: flex; align-items: center; gap: 10px; font-size: 22px; font-weight: 800; color: #fff; }
        .nav-brand img { height: 35px; }
        .btn-dash { background: transparent; border: 1px solid var(--accent); color: var(--accent); padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s ease;}
        .btn-dash:hover { background: var(--accent); color: #000; box-shadow: 0 0 15px var(--accent-glow); }

        .header-text { text-align: center; margin-bottom: 40px; }
        .header-text h1 { font-size: 36px; margin-bottom: 10px; background: linear-gradient(90deg, #fff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        
        .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; max-width: 1100px; margin: 0 auto; }
        .plan-card { background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); padding: 40px 30px; border-radius: 20px; transition: all 0.4s ease; position: relative; display: flex; flex-direction: column;}
        .plan-card:hover { border-color: var(--accent); transform: translateY(-10px); box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
        
        .popular-badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: linear-gradient(45deg, var(--accent), #58a6ff); color: #000; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
        
        .plan-title { font-size: 28px; font-weight: 800; color: #fff; margin-bottom: 15px; }
        .plan-price { font-size: 48px; font-weight: 800; color: #fff; margin-bottom: 5px; display: flex; align-items: baseline; gap: 5px;}
        .plan-price span { font-size: 16px; color: #8b949e; font-weight: 400;}
        .plan-desc { color: #8b949e; margin-bottom: 30px; font-size: 15px; border-bottom: 1px solid var(--border); padding-bottom: 20px;}
        
        .feature-list { list-style: none; margin-bottom: 30px; flex-grow: 1;}
        .feature-list li { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; font-size: 14px; color: #c9d1d9;}
        .feature-list svg { width: 18px; height: 18px; fill: var(--success); flex-shrink: 0;}
        
        .btn-pay { width: 100%; padding: 15px; border: none; border-radius: 10px; background: #21262d; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; display: flex; justify-content: center; align-items: center; gap: 10px;}
        .btn-pay:hover { background: #30363d; }
        .btn-pay.premium { background: var(--accent); color: #000; }
        .btn-pay.premium:hover { background: #d0aeff; box-shadow: 0 0 20px var(--accent-glow); }

        /* Modal Styles */
        .modal-overlay { position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.85); z-index: 100; display: none; justify-content:center; align-items:center; backdrop-filter: blur(10px); opacity: 0; transition: opacity 0.3s;}
        .modal-overlay.show { opacity: 1; }
        .modal { background: #0d1117; padding: 40px; border-radius: 20px; border: 1px solid var(--border); width: 90%; max-width: 450px; transform: scale(0.9); transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); box-shadow: 0 25px 50px rgba(0,0,0,0.5);}
        .modal-overlay.show .modal { transform: scale(1); }
        
        .input-group { margin-bottom: 20px; text-align: left; position: relative;}
        .input-group label { display: block; font-size: 13px; font-weight: 600; color: #8b949e; margin-bottom: 8px; }
        .input-group input { width: 100%; padding: 12px 15px 12px 40px; background: #050505; border: 1px solid var(--border); color: #fff; border-radius: 10px; outline: none; font-size: 14px; transition: 0.2s;}
        .input-group input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow);}
        .input-icon { position: absolute; left: 12px; top: 38px; width: 18px; height: 18px; fill: #8b949e; }

        .dashboard { max-width: 1000px; margin: 0 auto; display: none; animation: fadeIn 0.5s ease;}
        @keyframes fadeIn { from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);} }
        .token-card { background: var(--card); border: 1px solid var(--border); padding: 20px; border-radius: 12px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; transition: 0.2s;}
        .token-card:hover { border-color: #58a6ff; }
        .t-active { border-left: 5px solid var(--success); }
        .t-expired { border-left: 5px solid var(--border); opacity: 0.5; }
        
        .footer { text-align: center; margin-top: 60px; padding: 30px 0; border-top: 1px solid var(--border);}
        .trust-badges { display: flex; justify-content: center; gap: 20px; margin-bottom: 20px; }
        .trust-badges div { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #8b949e; }
        .footer-links a { color: #8b949e; text-decoration: none; margin: 0 15px; font-size: 13px; transition: 0.2s;}
        .footer-links a:hover { color: var(--accent); }
        
        /* Loading Spinner */
        .loader { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid var(--accent); border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: none;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <div id="toast-container"></div>

    <div class="navbar">
        <div class="nav-brand">
            <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="Qlynk Logo">
            Qlynk Host
        </div>
        <button class="btn-dash" onclick="openDashboard()">
            <svg style="width:16px;height:16px;vertical-align:middle;margin-right:5px;" viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
            My Tokens
        </button>
    </div>

    <div id="pricingSection">
        <div class="header-text">
            <h1>Choose Your Access Plan</h1>
            <p style="color:#8b949e;">Unlock secure, enterprise-grade file hosting and cinematic streaming.</p>
        </div>

        <div class="pricing-grid">
            <div class="plan-card">
                <div class="plan-title">Basic</div>
                <div class="plan-price">₹49<span>/ 24 Hours</span></div>
                <div class="plan-desc">Perfect for quick downloads and short-term access.</div>
                <ul class="feature-list">
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> 24 Hours Full Vault Access</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Standard Streaming Quality</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> PDF Receipt Included</li>
                </ul>
                <button class="btn-pay" onclick="selectPlan('basic')">Get Basic Access</button>
            </div>
            
            <div class="plan-card" style="border-color: var(--accent);">
                <div class="popular-badge">Most Popular</div>
                <div class="plan-title" style="color: var(--accent);">Pro</div>
                <div class="plan-price">₹99<span>/ 3 Days</span></div>
                <div class="plan-desc">The sweet spot for binging and extended projects.</div>
                <ul class="feature-list">
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> 72 Hours Unlimited Access</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> No Lag Streaming</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Ad Free Experience</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Best Isolated Streaming</li>
                </ul>
                <button class="btn-pay premium" onclick="selectPlan('pro')">Get Pro Access</button>
            </div>
            
            <div class="plan-card">
                <div class="plan-title">Ultra</div>
                <div class="plan-price">₹299<span>/ 7 Days</span></div>
                <div class="plan-desc">For heavy users who need uninterrupted reliability.</div>
                <ul class="feature-list">
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> 7 Days Continuous Access</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> No Lag Streaming</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Get Support For Request To add on QLYNK Tube</li>
                    <li><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> Best Isolated Streaming</li>
                </ul>
                <button class="btn-pay" onclick="selectPlan('ultra')">Get Ultra Access</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="userModal">
        <div class="modal">
            <h2 style="margin-bottom:10px; text-align:center; color:#fff;">Complete Your Order</h2>
            <p style="font-size:13px; color:#8b949e; text-align:center; margin-bottom:25px;">Secure connection established. Enter details for your receipt.</p>
            
            <div class="input-group">
                <label>Full Name</label>
                <svg class="input-icon" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                <input type="text" id="uName" placeholder="e.g. Deep Dey">
            </div>
            <div class="input-group">
                <label>Email Address</label>
                <svg class="input-icon" viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
                <input type="email" id="uEmail" placeholder="deep@example.com">
            </div>
            <div class="input-group">
                <label>Telegram Username (Start Bot First)</label>
                <svg class="input-icon" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                <input type="text" id="uTg" placeholder="@username">
            </div>
            
            <div style="text-align:center; margin-bottom:15px;">
                <a href="https://t.me/qlynknode_bot?start=xyz" target="_blank" style="color:var(--accent); font-size:12px; text-decoration:none; font-weight:800; background:rgba(188, 140, 255, 0.1); padding:8px 15px; border-radius:20px; border:1px solid var(--accent);">
                    🤖 Click here to Start Bot before paying!
                </a>
            </div>
            
            <button class="btn-pay premium" id="payBtn" onclick="initiatePayment()">
                <div class="loader" id="payLoader"></div>
                <span id="payText">Proceed to Secure Payment</span>
            </button>
            <button class="btn-pay" style="background:transparent; color:#8b949e; margin-top:10px;" onclick="closeModal()">Cancel</button>
        </div>
    </div>

    <div id="dashboardSection" class="dashboard">
        <h2 style="font-size:32px; margin-bottom:10px;">My Secure Vault</h2>
        <p style="color:#8b949e; margin-bottom:30px;">Manage your access tokens and download receipts.</p>
        
        <div style="display:flex; gap:15px; margin-bottom: 30px; flex-wrap: wrap;">
            <input type="email" id="dashEmail" placeholder="Enter your registered email" style="padding:15px; border-radius:10px; border:1px solid var(--border); background:#000; color:#fff; flex:1; min-width:250px; font-size:15px; outline:none;">
            <button class="btn-pay premium" style="width:auto; padding:0 30px;" onclick="fetchHistory()">Fetch History</button>
            <button class="btn-pay" style="width:auto; padding:0 30px; background:#21262d;" onclick="closeDashboard()">Back</button>
        </div>
        <div id="historyList"></div>
    </div>

    <div class="footer">
        <div class="trust-badges">
            <div><svg style="width:16px;fill:var(--success);" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg> 256-bit AES Encryption</div>
            <div><svg style="width:16px;fill:#58a6ff;" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg> Razorpay Secure</div>
        </div>
        <div class="footer-links">
            <a href="/terms">Terms of Service</a>
            <a href="/privacy">Privacy Policy</a>
            <a href="/refund">Refund Policy</a>
        </div>
        <p style="margin-top:20px; font-size:12px; color:#4b5563;">&copy; 2026 Qlynk Architecture. All rights reserved.</p>
    </div>

    <script>
        let selectedPlan = "";
        
        // --- Premium Toast Notification System ---
        function showToast(message, type="success") {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            const icon = type === 'success' ? `<svg style="width:20px;fill:var(--success);" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>` : `<svg style="width:20px;fill:var(--danger);" viewBox="0 0 24 24"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z"/></svg>`;
            toast.innerHTML = `${icon} <div>${message}</div>`;
            container.appendChild(toast);
            
            setTimeout(() => toast.classList.add('show'), 10);
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // --- Infinite Cookie Logic (10 Years) ---
        function setCookie(name, value) { document.cookie = `${name}=${value}; max-age=315360000; path=/`; }
        function getCookie(name) {
            let match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
            if (match) return match[2]; return "";
        }

        window.onload = () => {
            document.getElementById('uName').value = getCookie('q_name');
            document.getElementById('uEmail').value = getCookie('q_email');
            document.getElementById('uTg').value = getCookie('q_tg');
            document.getElementById('dashEmail').value = getCookie('q_email');
        };

        function selectPlan(planKey) {
            selectedPlan = planKey;
            const modalOverlay = document.getElementById('userModal');
            modalOverlay.style.display = 'flex';
            setTimeout(() => modalOverlay.classList.add('show'), 10);
        }

        function closeModal() {
            const modalOverlay = document.getElementById('userModal');
            modalOverlay.classList.remove('show');
            setTimeout(() => modalOverlay.style.display = 'none', 300);
        }

        function setBtnLoading(isLoading) {
            const text = document.getElementById('payText');
            const loader = document.getElementById('payLoader');
            const btn = document.getElementById('payBtn');
            if(isLoading) { text.style.display = 'none'; loader.style.display = 'block'; btn.disabled = true; } 
            else { text.style.display = 'block'; loader.style.display = 'none'; btn.disabled = false; }
        }

        async function initiatePayment() {
            const name = document.getElementById('uName').value.trim();
            const email = document.getElementById('uEmail').value.trim();
            const tg = document.getElementById('uTg').value.trim();
            
            if(!name || !email || !tg) return showToast("Please fill all security details.", "error");
            
            setCookie('q_name', name); setCookie('q_email', email); setCookie('q_tg', tg);
            setBtnLoading(true);

            try {
                // 1. Create Order
                const orderRes = await fetch('/api/payment/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ plan: selectedPlan, email: email })
                });
                const orderData = await orderRes.json();
                
                if(orderData.status !== "success") throw new Error(orderData.detail);

                // 2. Razorpay Options
                const options = {
                    "key": orderData.key_id,
                    "amount": orderData.amount,
                    "currency": "INR",
                    "name": "Qlynk Enterprise",
                    "description": `${selectedPlan.toUpperCase()} Node Access`,
                    "image": "https://qlynk.vercel.app/quicklink-logo.svg",
                    "order_id": orderData.order_id,
                    "handler": async function (response) {
                        // 3. Verify Payment
                        document.querySelector('.modal').innerHTML = `<div style="text-align:center; padding:30px 0;"><div class="loader" style="display:inline-block; width:40px; height:40px; border-width:4px; margin-bottom:20px;"></div><h2 style="color:var(--success)">Verifying Crypto Signature...</h2><p style="color:#8b949e; margin-top:10px;">Establishing secure token. Do not close.</p></div>`;
                        
                        const verifyRes = await fetch('/api/payment/verify', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_signature: response.razorpay_signature,
                                plan: selectedPlan, name: name, email: email, tg: tg
                            })
                        });
                        
                        const verifyData = await verifyRes.json();
                        if(verifyData.status === "success") {
                            const link = window.location.origin + `/view?token=${verifyData.token}`;
                            showToast("Payment Verified Successfully!");
                            document.querySelector('.modal').innerHTML = `
                                <div style="text-align:center;">
                                    <svg style="width:60px; fill:var(--success); margin-bottom:15px;" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                                    <h2 style="color:#fff; margin-bottom:10px;">Access Granted!</h2>
                                    <p style="margin-bottom:25px; font-size:14px; color:#8b949e;">Your dedicated node token is ready. Receipt sent via bot.</p>
                                    
                                    <div style="background:#000; border:1px solid var(--border); padding:15px; border-radius:10px; margin-bottom:20px;">
                                        <code style="color:var(--accent); word-break:break-all;">${link}</code>
                                    </div>

                                    <div style="display:flex; gap:15px; flex-direction:column;">
                                        <button class="btn-pay premium" onclick="navigator.clipboard.writeText('${link}'); showToast('Token Link Copied!');">Copy Link to Clipboard</button>
                                        <a href="${verifyData.receipt_url}" target="_blank" style="text-decoration:none;"><button class="btn-pay" style="background:#30363d;">Download PDF Receipt</button></a>
                                    </div>
                                    <button class="btn-dash" style="width:100%; margin-top:20px; border:none; color:#8b949e;" onclick="location.reload()">Return Home</button>
                                </div>
                            `;
                        } else { throw new Error("Cryptographic Verification Failed"); }
                    },
                    "modal": {
                        "ondismiss": async function() {
                            closeModal();
                            setBtnLoading(false);
                            showToast("Transaction Aborted", "error");
                            fetch('/api/payment/verify', {
                                method: 'POST', headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ cancel: true, order_id: orderData.order_id, plan: selectedPlan, name: name, email: email, tg: tg })
                            });
                        }
                    },
                    "prefill": { "name": name, "email": email, "contact": tg },
                    "theme": { "color": "#bc8cff" }
                };
                
                const rzp1 = new Razorpay(options);
                rzp1.open();
                
            } catch(e) {
                showToast(e.message || "Network Error. Please try again.", "error");
                setBtnLoading(false);
            }
        }

        // --- Dashboard Logic ---
        function openDashboard() {
            document.getElementById('pricingSection').style.display = 'none';
            document.getElementById('dashboardSection').style.display = 'block';
        }
        function closeDashboard() {
            document.getElementById('dashboardSection').style.display = 'none';
            document.getElementById('pricingSection').style.display = 'grid';
        }
        
        async function fetchHistory() {
            const email = document.getElementById('dashEmail').value.trim();
            if(!email) return showToast("Enter your registered email.", "error");
            
            setCookie('q_email', email);
            const listDiv = document.getElementById('historyList');
            listDiv.innerHTML = `<div style="text-align:center; padding:40px;"><div class="loader" style="display:inline-block; border-color:var(--border); border-top-color:var(--accent);"></div></div>`;
            
            try {
                const res = await fetch(`/api/user/history?email=${encodeURIComponent(email)}`);
                const data = await res.json();
                
                if(data.history.length === 0) {
                    listDiv.innerHTML = "<p style='color:#8b949e; text-align:center; padding:40px; background:var(--card); border-radius:10px;'>No purchase history found for this email.</p>"; return;
                }
                
                listDiv.innerHTML = data.history.reverse().slice(0, 5).map(h => {
                    const isActive = h.status === 'success' && new Date(h.expires_at) > new Date();
                    const styleClass = isActive ? 't-active' : 't-expired';
                    const statusText = isActive ? `<span style="color:var(--success); font-weight:600; font-size:12px;">● Active until ${h.expires_at.substring(0,10)}</span>` : `<span style="color:#8b949e; font-size:12px;">Expired</span>`;
                    
                    return `
                        <div class="token-card ${styleClass}">
                            <div>
                                <div style="font-weight:800; font-size:18px; margin-bottom:5px; color:#fff;">${h.plan_name.toUpperCase()} <span style="font-weight:400; color:#8b949e; font-size:14px;">- ₹${h.amount}</span></div>
                                <div style="font-size:12px; color:#8b949e; margin-bottom:8px;">Ord: ${h.order_id.substring(0,12)}... • ${h.date.substring(0,10)}</div>
                                ${statusText}
                            </div>
                            <div style="display:flex; flex-direction:column; gap:10px; align-items:flex-end;">
                                ${isActive ? `<button class="btn-pay premium" style="padding:8px 15px; font-size:12px;" onclick="navigator.clipboard.writeText('${window.location.origin}/view?token=${h.token}'); showToast('Token Copied!')">Copy Link</button>` : ''}
                                ${h.receipt_url ? `<a href="${h.receipt_url}" target="_blank" style="color:var(--accent); font-size:12px; text-decoration:none; font-weight:600;">Download PDF</a>` : ''}
                            </div>
                        </div>
                    `;
                }).join('');
            } catch(e) { 
                showToast("Error fetching database.", "error");
                listDiv.innerHTML = "";
            }
        }
    </script>
</body>
</html>
"""

# --- API ROUTES ---
@app.get("/checkout", response_class=HTMLResponse)
async def serve_checkout_page():
    if not is_checkout_enabled():
        return HTMLResponse(
            content="<body style='background:#050505; color:#8b949e; font-family:sans-serif; text-align:center; padding-top:100px;'><h2>🔒 Commercial Features are Disabled</h2><p>This node is operating in free/personal mode.</p></body>", 
            status_code=403
        )
    return HTMLResponse(content=CHECKOUT_UI_HTML)

class CreateOrderReq(BaseModel):
    plan: str
    email: str

@app.post("/api/payment/create")
async def create_rzp_order(req: CreateOrderReq, request: Request):
    if not is_checkout_enabled(): 
        raise HTTPException(status_code=403, detail="Checkout feature is disabled on this node.")
    # Security: IP Rate Limiting check
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Anti-Spam protection active.")
        
    if not rzp_client: raise HTTPException(status_code=500, detail="Razorpay Gateway offline.")
    if req.plan not in PLANS: raise HTTPException(status_code=400, detail="Invalid Plan Signature.")
    
    amount = PLANS[req.plan]["price_inr"] * 100 
    try:
        order = rzp_client.order.create({
            "amount": amount, "currency": "INR", "payment_capture": "1",
            "notes": {"email": req.email, "plan": req.plan, "ip": client_ip}
        })
        return {"status": "success", "order_id": order["id"], "amount": amount, "key_id": RZP_KEY}
    except Exception as e:
        logger.error(f"Order Gateway Error: {e}")
        raise HTTPException(status_code=500, detail="Could not mount payment order.")

class VerifyPaymentReq(BaseModel):
    cancel: bool = False
    order_id: str = None
    razorpay_payment_id: str = None
    razorpay_order_id: str = None
    razorpay_signature: str = None
    plan: str
    name: str
    email: str
    tg: str

@app.post("/api/payment/verify")
async def verify_rzp_payment(req: VerifyPaymentReq, request: Request):
    if not is_checkout_enabled(): 
        raise HTTPException(status_code=403, detail="Checkout feature is disabled on this node.")
    email_slug = re.sub(r'[^a-zA-Z0-9]', '_', req.email.lower())
    user_db = get_user_db(email_slug)
    
    # Update Profile Identity
    user_db["profile"]["name"] = req.name
    user_db["profile"]["email"] = req.email
    user_db["profile"]["tg"] = req.tg
    user_db["profile"]["last_ip"] = request.client.host
    
    current_time_iso = datetime.utcnow().isoformat() + "Z"
    
    # 1. Handle Canceled/Failed Payments
    if req.cancel:
        receipt_data = {
            "order_id": req.order_id, "date": current_time_iso, "status": "cancelled",
            "name": req.name, "email": req.email, "tg_contact": req.tg,
            "plan_name": PLANS[req.plan]["name"], "amount": PLANS[req.plan]["price_inr"],
            "reason": "User abandoned secure checkout."
        }
        pdf_path = generate_receipt_pdf(receipt_data)
        hf_pdf_path = f"users/{email_slug}/receipts/cancel_{req.order_id}.pdf"
        api.upload_file(path_or_fileobj=pdf_path, path_in_repo=hf_pdf_path, repo_id=DATASET_REPO, repo_type="dataset")
        
        receipt_data["receipt_url"] = f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/main/{hf_pdf_path}"
        user_db["history"].append(receipt_data)
        save_user_db(email_slug, user_db)
        
        # Bot remarketing
        await send_tg_receipt(req.tg, f"❌ Oops! Your Qlynk {PLANS[req.plan]['name']} checkout was cancelled. If you changed your mind, you can re-initiate anytime at {STATIC_DOMAIN}/checkout.", pdf_path)
        return {"status": "cancelled"}

    # 2. Verify Successful Cryptographic Signature
    try:
        rzp_client.utility.verify_payment_signature({
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'razorpay_signature': req.razorpay_signature
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Cryptographic Signature Failed. Hack attempt logged.")

    # 3. Generate Dedicated Token
    plan_days = PLANS[req.plan]["days"]
    new_token = uuid.uuid4().hex
    expiry_time = time.time() + (plan_days * 86400)
    
    token_db = get_tokens_db()
    token_db["tokens"][new_token] = {
        "expires_at": expiry_time, "status": "active", "created_at": current_time_iso, "email": req.email
    }
    save_tokens_db(token_db)
    
    # 4. Generate Success Invoice PDF
    receipt_data = {
        "order_id": req.razorpay_order_id, "date": current_time_iso, "status": "success",
        "name": req.name, "email": req.email, "tg_contact": req.tg,
        "plan_name": PLANS[req.plan]["name"], "amount": PLANS[req.plan]["price_inr"],
        "token": new_token, "expires_at": datetime.fromtimestamp(expiry_time).isoformat() + "Z"
    }
    pdf_path = generate_receipt_pdf(receipt_data)
    hf_pdf_path = f"users/{email_slug}/receipts/success_{req.razorpay_order_id}.pdf"
    
    api.upload_file(path_or_fileobj=pdf_path, path_in_repo=hf_pdf_path, repo_id=DATASET_REPO, repo_type="dataset")
    
    receipt_data["receipt_url"] = f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/main/{hf_pdf_path}"
    user_db["history"].append(receipt_data)
    save_user_db(email_slug, user_db)
    
    # 5. Enterprise Telegram Alert
    msg = f"🎉 **Payment Authorized & Verified!**\n\nPlan: {PLANS[req.plan]['name']}\nAmount: ₹{PLANS[req.plan]['price_inr']}\n\nHere is your secure access link:\n{STATIC_DOMAIN}/view?token={new_token}\n\nOfficial PDF Receipt is attached."
    await send_tg_receipt(req.tg, msg, pdf_path)
    
    return {"status": "success", "token": new_token, "receipt_url": receipt_data["receipt_url"]}

@app.get("/api/user/history")
async def get_user_history(email: str):
    email_slug = re.sub(r'[^a-zA-Z0-9]', '_', email.lower())
    db = get_user_db(email_slug)
    return {"history": db.get("history", [])}            

# ==========================================
# 15. LEGAL & COMPLIANCE PAGES (Dynamic Routing)
# ==========================================

# --- Premium Master HTML Template ---
def generate_legal_page(title: str, content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Qlynk - {title}</title>
        <link rel="icon" type="image/png" href="https://qlynk.vercel.app/quicklink-logo.png">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            :root {{ --bg: #050505; --card: rgba(22, 27, 34, 0.6); --accent: #bc8cff; --text: #e1e4e8; --text-muted: #8b949e; --border: #30363d; }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
            body {{ background: var(--bg); color: var(--text); background-image: radial-gradient(circle at top, #1a1a2e 0%, transparent 40%); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 20px; line-height: 1.6;}}
            
            .navbar {{ width: 100%; max-width: 900px; display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 40px; }}
            .nav-brand {{ display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 800; color: #fff; text-decoration: none; }}
            .nav-brand img {{ height: 30px; }}
            .btn-back {{ background: #21262d; color: #fff; text-decoration: none; padding: 8px 16px; border-radius: 8px; font-size: 14px; font-weight: 600; border: 1px solid var(--border); transition: 0.3s; }}
            .btn-back:hover {{ background: var(--accent); color: #000; border-color: var(--accent); }}
            
            .content-box {{ width: 100%; max-width: 900px; background: var(--card); backdrop-filter: blur(20px); border: 1px solid var(--border); padding: 50px; border-radius: 20px; margin-bottom: 50px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }}
            
            .page-title {{ font-size: 36px; font-weight: 800; margin-bottom: 10px; background: linear-gradient(90deg, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .last-updated {{ font-size: 13px; color: var(--text-muted); margin-bottom: 40px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
            
            .legal-content h2 {{ font-size: 20px; color: #fff; margin: 30px 0 15px 0; }}
            .legal-content p {{ color: var(--text-muted); margin-bottom: 15px; font-size: 15px; }}
            .legal-content ul {{ color: var(--text-muted); margin-bottom: 15px; padding-left: 20px; font-size: 15px; }}
            .legal-content li {{ margin-bottom: 8px; }}
            .legal-content a {{ color: var(--accent); text-decoration: none; }}
            .legal-content a:hover {{ text-decoration: underline; }}
            
            @media (max-width: 768px) {{ .content-box {{ padding: 30px 20px; }} .page-title {{ font-size: 28px; }} }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <a href="/" class="nav-brand">
                <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="Qlynk">
                Qlynk Node
            </a>
            <a href="/checkout" class="btn-back">Return to Checkout</a>
        </div>
        
        <div class="content-box">
            <h1 class="page-title">{title}</h1>
            <div class="last-updated">Last Updated: April 2026 | Governing Authority: Qlynk Architecture</div>
            <div class="legal-content">
                {content}
            </div>
        </div>
        
        <div style="text-align:center; color:var(--text-muted); font-size:12px; margin-bottom:20px;">
            &copy; 2026 Qlynk Architecture. Engineered by Deep Dey. All rights reserved.
        </div>
    </body>
    </html>
    """

# --- 1. Terms of Service Content ---
TERMS_CONTENT = """
<h2>1. Acceptance of Terms</h2>
<p>By accessing and using the Qlynk Node ecosystem, including the Secure File Vault and Qlynk Tube streaming capabilities, you agree to comply with and be bound by these Terms of Service. If you do not agree to these terms, please do not use our services.</p>

<h2>2. Service Description & Access</h2>
<p>Qlynk provides enterprise-grade, decentralized file hosting and media streaming utilizing Hugging Face Datasets infrastructure. Access to premium bandwidth, high-definition streaming, and dedicated node tokens requires a valid commercial pass obtained via our secure checkout.</p>
<ul>
    <li>Tokens are generated per user and are strictly non-transferable.</li>
    <li>We reserve the right to modify or discontinue any part of the service with or without notice.</li>
</ul>

<h2>3. User Conduct & Acceptable Use</h2>
<p>You agree not to use the Qlynk infrastructure for any unlawful purpose. The following activities are strictly prohibited:</p>
<ul>
    <li>Hosting or transmitting malware, viruses, or malicious code.</li>
    <li>Bypassing or attempting to crack our cryptographic token system.</li>
    <li>Using automated scraping tools or bots against our API without authorization.</li>
</ul>

<h2>4. Termination of Access</h2>
<p>Qlynk Architecture reserves the right to terminate or suspend your access to the node immediately, without prior notice or liability, for any reason whatsoever, including without limitation if you breach the Terms.</p>
"""

# --- 2. Privacy Policy Content ---
PRIVACY_CONTENT = """
<h2>1. Information We Collect</h2>
<p>At Qlynk, we prioritize your privacy. During the checkout process and general usage, we collect strictly necessary data to provision your tokens and ensure security:</p>
<ul>
    <li><strong>Identity Data:</strong> Name, Email address, and Telegram/Phone contact details for receipt delivery.</li>
    <li><strong>Technical Data:</strong> IP addresses, browser types, and device information for security routing and anti-spam measures.</li>
    <li><strong>Transaction Data:</strong> Secure Payment IDs provided by Razorpay (We do NOT store your credit card or UPI PINs).</li>
</ul>

<h2>2. How We Use Your Data</h2>
<p>Your data is utilized exclusively for providing and improving the Qlynk service. Specifically, we use it to:</p>
<ul>
    <li>Generate secure, personalized access tokens.</li>
    <li>Send automated PDF receipts and notifications via our official Telegram Bot.</li>
    <li>Prevent fraud and enforce our Anti-Spam Rate Limiting protocols.</li>
</ul>

<h2>3. Data Storage & Security</h2>
<p>Your profile data is stored securely within isolated folders inside the Hugging Face Vault architecture. We employ 256-bit encryption for data in transit. You have the right to request deletion of your data logs by contacting the administrator.</p>

<h2>4. Cookies & Local Storage</h2>
<p>We use ultra-long-lasting cookies (approx. 10 years) strictly to enhance your user experience by auto-filling your details during repeat checkouts. You can clear these at any time via your browser settings.</p>
"""

# --- 3. Refund Policy Content ---
REFUND_CONTENT = """
<h2>1. General Refund Policy</h2>
<p>Due to the digital nature of our services (Node Tokens, Streaming Bandwidth, Vault Access), <strong>all sales are generally final once a token has been generated and utilized</strong>. Instant digital delivery means the service is consumed immediately upon access.</p>

<h2>2. Eligible Refund Conditions</h2>
<p>We believe in fairness. Refunds or token extensions will only be issued under the following circumstances:</p>
<ul>
    <li><strong>System Failure:</strong> If the Qlynk Node experiences an extended global outage (exceeding 12 hours) during your active premium window.</li>
    <li><strong>Cryptographic Errors:</strong> If a token generated by our system fails to grant you access due to an internal backend error.</li>
    <li><strong>Accidental Double Charges:</strong> If the Razorpay gateway accidentally bills you twice for a single order.</li>
</ul>

<h2>3. Non-Refundable Scenarios</h2>
<p>Refunds will <strong>NOT</strong> be provided if:</p>
<ul>
    <li>You simply change your mind after the token has been issued.</li>
    <li>Your token expires because you forgot to use it within the allotted time (24h, 3 Days, or 7 Days).</li>
    <li>Your access is terminated due to a violation of our Terms of Service.</li>
</ul>

<h2>4. How to Request a Refund</h2>
<p>If you believe you are eligible for a refund due to a technical fault, please contact the administrator via the Telegram Bot or Discord channel. You must provide your <strong>Order ID</strong> (found on your PDF receipt) for verification. Approved refunds are processed within 5-7 business days.</p>
"""

# --- API ROUTES ---

@app.get("/terms", response_class=HTMLResponse)
async def serve_terms_page():
    return HTMLResponse(content=generate_legal_page("Terms of Service", TERMS_CONTENT))

@app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy_page():
    return HTMLResponse(content=generate_legal_page("Privacy Policy", PRIVACY_CONTENT))

@app.get("/refund", response_class=HTMLResponse)
async def serve_refund_page():
    return HTMLResponse(content=generate_legal_page("Refund Policy", REFUND_CONTENT))

# ==========================================
# END OF FILE
# ==========================================

# ==========================================
# 16. ISOLATED AI HELPDESK & SUPPORT SYSTEM
# ==========================================
from pyrogram import StopPropagation, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import re
from datetime import datetime
from huggingface_hub import hf_hub_download

# --- Support Globals ---
support_states = {} # Track users in support flow
active_tickets = {} # Track active tickets
owner_chat_state = {} # Track admin's current support action

def get_faq_db():
    try:
        path = hf_hub_download(repo_id=DATASET_REPO, filename="support_faq.json", repo_type="dataset", token=HF_TOKEN)
        with open(path, "r") as f: return json.load(f)
    except: return {"faqs": []} # Fallback if JSON doesn't exist yet

def save_ticket_history(email_slug, ticket_id, history, status="closed"):
    try:
        user_db = get_user_db(email_slug)
        user_db.setdefault("tickets", []).append({"ticket_id": ticket_id, "status": status, "closed_at": datetime.utcnow().isoformat() + "Z", "history": history})
        save_user_db(email_slug, user_db)
    except Exception as e: logger.error(f"Failed to save ticket: {e}")

# --- 1. SUPPORT INITIATOR ---
# --- 1. SUPPORT INITIATOR ---
@tg_app.on_message(filters.command("support"))
async def support_cmd(client, message):
    user_id = message.from_user.id
    
    if user_id in support_states:
        await message.reply_text("⚠️ You are already in a support session. Type your query or /cancel.")
        return
        
    support_states[user_id] = {"step": "email"}
    await message.reply_text("🎧 **Qlynk Auto-Support System**\n\nPlease enter your **Registered Email ID** to verify your account:")

# --- 2. ADMIN CLOSE COMMAND ---
@tg_app.on_message(filters.command("close"))
async def close_ticket_cmd(client, message):
    owner_id = message.from_user.id
    if not is_auth(owner_id): return
    
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Syntax: `/close [ticket_id]`\nExample: `/close TCK-1A2B3C`")
        
    ticket_id = message.command[1].strip()
    if ticket_id not in active_tickets:
        return await message.reply_text("❌ Ticket not found or already closed.")
        
    t_data = active_tickets[ticket_id]
    
    save_ticket_history(t_data["email_slug"], ticket_id, t_data["history"], "closed_by_admin")
    
    try: await client.send_message(t_data["user_id"], f"🔒 **Ticket {ticket_id} has been closed by the Admin.**\nAll chat logs have been secured in your vault. Thank you!")
    except: pass
    
    if t_data["user_id"] in support_states: del support_states[t_data["user_id"]]
    if owner_id in owner_chat_state: del owner_chat_state[owner_id]
    del active_tickets[ticket_id]
    
    await message.reply_text(f"✅ **Ticket {ticket_id} Closed.**\nChat history permanently archived in the user's dataset folder.")

# --- 3. THE SHIELD INTERCEPTOR (Group -1 runs before anything else) ---
@tg_app.on_message((filters.text | filters.media | filters.document) & ~filters.command(["start", "verify", "logout", "batch", "connect", "index", "support", "close"]), group=-1)
async def support_interceptor(client, message):
    user_id = message.from_user.id
    text_content = message.text or message.caption or ""
    
    # A. ADMIN ACTION ROUTING
    if user_id in owner_chat_state:
        state = owner_chat_state[user_id]
        ticket_id = state["ticket_id"]
        t_data = active_tickets.get(ticket_id)
        
        if t_data:
            if state["action"] == "chatting":
                if message.text: await client.send_message(t_data["user_id"], f"👨‍💻 **Admin:**\n{message.text}")
                else: await client.copy_message(t_data["user_id"], message.chat.id, message.id, caption=f"👨‍💻 **Admin:**\n{message.caption or ''}")
                t_data["history"].append({"sender": "admin", "text": message.text or "[Media Attached]"})
                raise StopPropagation 
                
            elif state["action"] == "rejecting":
                reason = message.text or "No specific reason provided."
                await client.send_message(t_data["user_id"], f"❌ **Your support request was declined.**\n\n**Reason:** {reason}\n\n*Ticket {ticket_id} closed.*")
                t_data["history"].append({"sender": "system", "text": f"Ticket Rejected. Reason: {reason}"})
                save_ticket_history(t_data["email_slug"], ticket_id, t_data["history"], "rejected")
                
                del active_tickets[ticket_id]
                del owner_chat_state[user_id]
                if t_data["user_id"] in support_states: del support_states[t_data["user_id"]]
                await message.reply_text(f"✅ Ticket {ticket_id} rejected and user notified.")
                raise StopPropagation

    # B. USER SUPPORT FLOW
    if user_id in support_states:
        state = support_states[user_id]
        
        if message.text and message.text.lower() == "/cancel":
            del support_states[user_id]
            await message.reply_text("❌ Support session cancelled.")
            raise StopPropagation

        if state["step"] == "email":
            email = text_content.strip()
            email_slug = re.sub(r'[^a-zA-Z0-9]', '_', email.lower())
            state["email"] = email
            state["email_slug"] = email_slug
            state["step"] = "ai_bot"
            await message.reply_text("🤖 **Account Verified. I am the Qlynk AI Assistant.**\n\nPlease describe your problem. I will try to solve it instantly!")
            raise StopPropagation
            
        elif state["step"] == "ai_bot":
            if not message.text:
                await message.reply_text("I can only process text right now. Please describe your issue in words.")
                raise StopPropagation
                
            query = message.text.lower()
            state["last_query"] = message.text 
            faq_db = get_faq_db()
            found_answer = None
            
            for item in faq_db.get("faqs", []):
                for kw in item.get("keywords", []):
                    if kw in query:
                        found_answer = item.get("answer")
                        break
                if found_answer: break
                
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, this solved it", callback_data="faq_solve")],
                [InlineKeyboardButton("🗣️ No, Talk to a Human", callback_data="faq_human")]
            ])
            
            if found_answer: await message.reply_text(f"💡 **Here is what I found:**\n\n{found_answer}", reply_markup=kb)
            else: await message.reply_text("I couldn't find an automatic solution for that. Would you like me to connect you with our human support team?", reply_markup=kb)
            raise StopPropagation
            
        elif state["step"] == "chatting":
            ticket_id = state.get("ticket_id")
            t_data = active_tickets.get(ticket_id)
            if t_data:
                t_data["history"].append({"sender": "user", "text": text_content})
                admin_id = state.get("admin_id")
                if admin_id:
                    if message.text: await client.send_message(admin_id, f"👤 **User:**\n{message.text}")
                    else: await client.copy_message(admin_id, message.chat.id, message.id, caption=f"👤 **User:**\n{message.caption or ''}")
            raise StopPropagation

# --- 4. ISOLATED CALLBACK BUTTONS (Only triggers for support buttons) ---
@tg_app.on_callback_query(filters.regex(r"^(faq_|accept_|reject_)"), group=-1)
async def support_button_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    if data == "faq_solve":
        if user_id in support_states: del support_states[user_id]
        await query.message.edit_text("Awesome! Glad I could help. Support session closed. 🎉")
        
    elif data == "faq_human":
        if user_id not in support_states: return
        state = support_states[user_id]
        
        ticket_id = f"TCK-{uuid.uuid4().hex[:6].upper()}"
        state["ticket_id"] = ticket_id
        state["step"] = "waiting_admin"
        
        active_tickets[ticket_id] = {
            "user_id": user_id, "email_slug": state["email_slug"], 
            "history": [{"sender": "user", "text": state.get("last_query", "User requested human support.")}]
        }
        
        await query.message.edit_text(f"🎫 **Ticket {ticket_id} Created!**\n\nForwarding your issue to the core team. Please hold on...")
        
        owners = get_tg_auth_db().get("authorized_users", [])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Accept & Chat", callback_data=f"accept_{ticket_id}")],
            [InlineKeyboardButton("❌ Reject Ticket", callback_data=f"reject_{ticket_id}")]
        ])
        for owner in owners:
            try: await client.send_message(owner, f"🚨 **Human Support Required** | `{ticket_id}`\n👤 **User:** {state['email']}\n\n**Query:**\n{state.get('last_query')}", reply_markup=kb)
            except: pass

    elif data.startswith("accept_"):
        ticket_id = data.split("_")[1]
        if ticket_id not in active_tickets: return await query.answer("Ticket invalid or closed.", show_alert=True)
        
        t_data = active_tickets[ticket_id]
        target_user = t_data["user_id"]
        
        support_states[target_user]["step"] = "chatting"
        support_states[target_user]["admin_id"] = user_id
        owner_chat_state[user_id] = {"action": "chatting", "ticket_id": ticket_id}
        
        await query.message.edit_text(query.message.text + f"\n\n🟢 **YOU ACCEPTED THIS TICKET.**\n(Type to chat. Use `/close {ticket_id}` to end.)")
        try: await client.send_message(target_user, "👨‍💻 **An Admin has joined the chat.** How can I help you today?")
        except: pass

    elif data.startswith("reject_"):
        ticket_id = data.split("_")[1]
        if ticket_id not in active_tickets: return await query.answer("Ticket invalid.", show_alert=True)
        
        owner_chat_state[user_id] = {"action": "rejecting", "ticket_id": ticket_id}
        await query.message.edit_text(query.message.text + f"\n\n🔴 **YOU ARE REJECTING THIS TICKET.**")
        await client.send_message(user_id, f"Please type the reason for rejecting ticket `{ticket_id}`. (This will be sent directly to the user).")
        
    raise StopPropagation # Prevents these buttons from going to your other handlers

# ==========================================
# 17. DYNAMIC SLUG ROTATOR (MOVING TARGET DEFENSE)
# ==========================================
import random

async def dynamic_slug_rotator():
    logger.info("🛡️ Dynamic Slug Rotator Initialized. Standing by...")
    # Thoda wait karega server start hone ke baad (taki crash na ho)
    await asyncio.sleep(600) 
    
    while True:
        # Generate random sleep time between 6 hours (21600s) and 24 hours (86400s)
        sleep_time = random.randint(21600, 86400)
        hours = sleep_time / 3600
        logger.info(f"🕒 Next Slug Rotation scheduled in {hours:.2f} hours.")
        
        await asyncio.sleep(sleep_time)
        logger.info("🔄 Initiating Global Slug Rotation for Security...")
        
        try:
            db = get_db()
            sub_db = get_sub_db()
            
            files = db.get("files", [])
            subs = sub_db.get("subtitles", [])
            
            # Dictionary to map Old Slug -> New Slug
            slug_map = {}
            
            # 1. Generate new 32-char slugs for all files
            # 1. Generate new 32-char slugs (SKIP IMAGES, ONLY ROTATE VIDEOS/DOCS)
            # Yahan hum RAM (files list) mein hi sab edit kar rahe hain. 
            # Baad mein ek hi save_db() se upload ho jayega (Total 2 API calls only).
            # 1. Generate new 32-char slugs (STRICT: ONLY ROTATE VIDEOS & AUDIOS)
            # Yahan hum RAM (files list) mein hi sab edit kar rahe hain.
            rotated_count = 0
            for f in files:
                mime = str(f.get("mime_type", "")).lower()
                
                # Sirf aur Sirf Video aur Audio ka slug change hoga (Images & Docs skipped)
                if mime.startswith("video/") or mime.startswith("audio/"):
                    old_slug = f["slug"]
                    new_slug = uuid.uuid4().hex
                    slug_map[old_slug] = new_slug
                    f["slug"] = new_slug
                    rotated_count += 1
            
            # 2. Fix Internal Thumbnail Links
            for f in files:
                if f.get("thumbnail", "").startswith("/f/"):
                    old_t_slug = f["thumbnail"].replace("/f/", "")
                    if old_t_slug in slug_map:
                        f["thumbnail"] = f"/f/{slug_map[old_t_slug]}"
            
            # 3. Fix Subtitle Linkages
            for s in subs:
                if s["media_slug"] in slug_map:
                    s["media_slug"] = slug_map[s["media_slug"]]
            
            # 4. Save Everything Back to Datacenter
            db["files"] = files
            save_db(db)
            
            sub_db["subtitles"] = subs
            save_sub_db(sub_db)
            
            logger.info(f"✅ HIGH SECURITY: Rotated {rotated_count} media slugs. Images and Docs skipped to keep links stable!")
        except Exception as e:
            logger.error(f"❌ Slug Rotator Error: {e}")

# ==========================================
# 18. THE MASTER ADMIN DASHBOARD (VIRTUAL OS)
# ==========================================

# ==========================================
# 18. THE MASTER ADMIN DASHBOARD (VIRTUAL OS)
# ==========================================

class BulkDeleteReq(BaseModel):
    slugs: List[str]

@app.delete("/api/admin/bulk_delete")
async def bulk_delete_files(req: BulkDeleteReq, token: str = Depends(verify_auth)):
    db = get_db()
    files_list = db.get("files", [])
    
    deleted_count = 0
    for slug in req.slugs:
        file_record = next((item for item in files_list if item["slug"] == slug), None)
        if file_record:
            try:
                api.delete_file(path_in_repo=file_record["path"], repo_id=DATASET_REPO, repo_type="dataset")
            except Exception as e:
                logger.warning(f"File {slug} might already be deleted from HF: {e}")
            files_list = [item for item in files_list if item["slug"] != slug]
            deleted_count += 1
            
    db["files"] = files_list
    save_db(db)
    return {"status": "success", "message": f"{deleted_count} files securely wiped from Datacenter."}

@app.get("/api/admin/tokens")
async def get_all_tokens(token: str = Depends(verify_auth)):
    return get_tokens_db()

class CreateCustomTokenReq(BaseModel):
    valid_hours: int
    session_days: int
    max_users: int

@app.post("/api/admin/token/create")
async def admin_create_token(req: CreateCustomTokenReq, token: str = Depends(verify_auth)):
    new_token = uuid.uuid4().hex
    db = get_tokens_db()
    
    # Advanced Token Configuration
    db["tokens"][new_token] = {
        "expires_at": time.time() + (req.valid_hours * 3600),
        "status": "active",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "email": "Admin Vault Gen",
        "config": {
            "max_users": req.max_users,
            "session_days": req.session_days
        },
        "active_sessions": 0 # Counter for logged in devices
    }
    save_tokens_db(db)
    return {"status": "success", "token": new_token}

@app.delete("/api/admin/token/{token_id}")
async def delete_custom_token(token_id: str, token: str = Depends(verify_auth)):
    db = get_tokens_db()
    if token_id in db["tokens"]:
        del db["tokens"][token_id]
        save_tokens_db(db)
        return {"status": "success", "message": "Token deleted. All users auto-logged out."}
    raise HTTPException(status_code=404, detail="Token not found.")

@app.post("/api/admin/token/revoke/{token_id}")
async def revoke_token_sessions(token_id: str, token: str = Depends(verify_auth)):
    db = get_tokens_db()
    if token_id in db["tokens"]:
        # Resets the active user count and changes the internal salt to force re-auth
        db["tokens"][token_id]["active_sessions"] = 0
        db["tokens"][token_id]["session_salt"] = uuid.uuid4().hex 
        save_tokens_db(db)
        return {"status": "success", "message": "All active sessions cleared instantly."}
    raise HTTPException(status_code=404, detail="Token not found.")

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qlynk Master Console</title>
    <link rel="icon" type="image/png" href="https://qlynk.vercel.app/quicklink-logo.png">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        :root { --bg: #050505; --card: #161b22; --accent: #bc8cff; --text: #e1e4e8; --border: #30363d; --danger: #da3633; --success: #2ea043; --warn: #d29922;}
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text); overflow-x: hidden; }
        
        /* MOBILE ENFORCEMENT SHIELD */
        #mobile-blocker { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:#000; z-index:9999; justify-content:center; align-items:center; flex-direction:column; padding:30px; text-align:center;}
        @media (max-width: 1024px) { 
            #app-layout { display: none !important; }
            #mobile-blocker { display: flex; }
        }

        #app-layout { display: flex; height: 100vh; }
        
        /* SIDEBAR */
        .sidebar { width: 260px; background: var(--card); border-right: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; gap: 10px;}
        .brand { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 30px; display: flex; align-items: center; gap: 10px;}
        .brand img { height: 26px; }
        .nav-btn { background: transparent; color: #8b949e; border: none; padding: 12px 15px; text-align: left; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; display: flex; align-items: center; gap: 10px;}
        .nav-btn:hover { background: rgba(255,255,255,0.05); color: #fff;}
        .nav-btn.active { background: rgba(188, 140, 255, 0.1); color: var(--accent); border: 1px solid rgba(188, 140, 255, 0.3);}
        
        /* MAIN CONTENT */
        .main-content { flex: 1; padding: 40px; overflow-y: auto; background-image: radial-gradient(circle at top right, #1a1a2e 0%, transparent 40%);}
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;}
        h1 { font-size: 28px; font-weight: 800; color: #fff;}
        
        /* TABS */
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);} }

        /* DATA TABLE */
        .table-container { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);}
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;}
        th, td { padding: 12px 20px; border-bottom: 1px solid var(--border); vertical-align: middle;}
        th { background: #0d1117; color: #8b949e; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px;}
        tr:hover { background: rgba(255,255,255,0.02); }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .b-vid { background: rgba(188,140,255,0.2); color: var(--accent); }
        .b-doc { background: rgba(88,166,255,0.2); color: #58a6ff; }
        .b-ext { background: rgba(218,54,51,0.2); color: var(--danger); }
        
        /* THUMBNAILS */
        .row-thumb { width: 45px; height: 30px; object-fit: cover; border-radius: 4px; border: 1px solid var(--border); cursor: pointer; transition: 0.2s; background: #000;}
        .row-thumb:hover { transform: scale(1.1); border-color: var(--accent);}
        
        /* ACTION BAR & BUTTONS */
        .action-bar { background: rgba(218,54,51,0.1); border: 1px solid var(--danger); padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: none; justify-content: space-between; align-items: center;}
        .action-bar.show { display: flex; }
        .btn { background: #21262d; color: #fff; border: 1px solid var(--border); padding: 8px 15px; border-radius: 6px; font-weight: 600; cursor: pointer; transition: 0.2s;}
        .btn:hover { background: #30363d; }
        .btn-danger { background: var(--danger); color: #fff; border: none; }
        .btn-danger:hover { background: #ff5c5c; }
        .btn-primary { background: var(--accent); color: #000; border: none;}
        .btn-primary:hover { background: #d0aeff; box-shadow: 0 0 15px rgba(188,140,255,0.4);}
        .icon-btn { background: transparent; border: none; font-size: 16px; cursor: pointer; transition: 0.2s; opacity: 0.7;}
        .icon-btn:hover { opacity: 1; transform: scale(1.2);}
        
        /* PREVIEW UNIVERSAL MODAL */
        .modal-overlay { position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.9); z-index: 10000; display: none; justify-content:center; align-items:center; backdrop-filter: blur(5px);}
        .modal-overlay.show { display: flex; }
        .modal-box { background: var(--card); border: 1px solid var(--border); width: 90%; max-width: 1000px; border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; max-height: 90vh; box-shadow: 0 25px 50px rgba(0,0,0,0.8);}
        .modal-header { padding: 15px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: #0d1117;}
        .modal-body { padding: 0; flex: 1; overflow-y: auto; background: #000; display: flex; justify-content: center; align-items: center; min-height: 400px;}
        
        /* PREVIEW ELEMENTS */
        .preview-video { width: 100%; max-height: 70vh; outline: none; }
        .preview-img { max-width: 100%; max-height: 70vh; object-fit: contain; }
        .preview-code { width: 100%; height: 100%; min-height: 400px; padding: 20px; background: #0d1117; color: #3fb950; font-family: monospace; font-size: 13px; white-space: pre-wrap; overflow-x: auto; margin: 0;}

        /* TOKEN FORGE CARD */
        .forge-card { background: var(--card); border: 1px solid var(--accent); padding: 25px; border-radius: 12px; margin-bottom: 30px; display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap; box-shadow: 0 0 20px rgba(188,140,255,0.1);}
        .input-group { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 150px;}
        .input-group label { font-size: 12px; color: #8b949e; font-weight: bold; text-transform: uppercase;}
        .input-group input { background: #0d1117; border: 1px solid var(--border); color: #fff; padding: 10px 15px; border-radius: 6px; outline: none;}
        .input-group input:focus { border-color: var(--accent); }
        
        .loader { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid var(--accent); border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 50px auto;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <div id="mobile-blocker">
        <svg style="width:60px; fill:var(--danger); margin-bottom:20px;" viewBox="0 0 24 24"><path d="M19 1H5c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V3c0-1.1-.9-2-2-2zm0 18H5V5h14v14zM8 14l3 3 5-5-1.41-1.41L11 14.17l-1.59-1.59L8 14z"/></svg>
        <h2 style="color:#fff; margin-bottom:10px;">Security Protocol Active</h2>
        <p style="color:#8b949e; font-size:14px; max-width:300px;">The Master Admin OS requires a high-resolution display for full control. Please access this terminal from a Desktop browser.</p>
    </div>

    <div class="modal-overlay" id="previewModal">
        <div class="modal-box">
            <div class="modal-header">
                <h3 id="previewTitle" style="font-size:16px; color:#fff; display:-webkit-box; -webkit-line-clamp:1; overflow:hidden;">Asset Preview</h3>
                <button class="btn" style="padding: 5px 10px; background:transparent; border-color:transparent;" onclick="closePreview()">❌ Close</button>
            </div>
            <div class="modal-body" id="previewBody">
                <div class="loader"></div>
            </div>
        </div>
    </div>

    <div id="app-layout">
        <div class="sidebar">
            <div class="brand">
                <img src="https://qlynk.vercel.app/quicklink-logo.svg" alt="Qlynk">
                Master OS
            </div>
            <button class="nav-btn active" onclick="switchTab('files', this)">📂 Asset Vault</button>
            <button class="nav-btn" onclick="switchTab('tokens', this)">🔑 Token Control</button>
            <button class="nav-btn" onclick="switchTab('health', this)">📡 Server Health</button>
            <button class="nav-btn" style="margin-top:auto; color:var(--danger);" onclick="window.location.href='/'">🚪 Exit Terminal</button>
        </div>

        <div class="main-content">
            
            <div id="tab-files" class="tab-content active">
                <div class="header">
                    <h1>Vault Management</h1>
                    <span style="color:#8b949e; font-size:14px;" id="total-files-count">Loading...</span>
                </div>
                
                <div class="action-bar" id="actionBar">
                    <span style="color:var(--danger); font-weight:bold;" id="selectedCount">0 files selected</span>
                    <button class="btn btn-danger" onclick="executeBulkDelete()">Delete Selected Files</button>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 40px;"><input type="checkbox" id="selectAll" onchange="toggleAll(this)"></th>
                                <th style="width: 60px;">Media</th>
                                <th>File Name / Title</th>
                                <th>Size</th>
                                <th>Engine Type</th>
                                <th>Date Added</th>
                            </tr>
                        </thead>
                        <tbody id="filesTableBody">
                            <tr><td colspan="6"><div class="loader"></div></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-tokens" class="tab-content">
                <div class="header">
                    <h1>Premium Token Matrix</h1>
                </div>

                <div class="forge-card">
                    <div style="width:100%; font-size:14px; font-weight:bold; color:var(--accent); margin-bottom:10px;">🛠️ Generate Custom Token</div>
                    <div class="input-group">
                        <label>Max Users Allowed</label>
                        <input type="number" id="tUsers" value="1" min="1">
                    </div>
                    <div class="input-group">
                        <label>Token Valid For (Hours)</label>
                        <input type="number" id="tHours" value="24" min="1">
                    </div>
                    <div class="input-group">
                        <label>Session Length (Days)</label>
                        <input type="number" id="tDays" value="7" min="1">
                    </div>
                    <button class="btn btn-primary" style="height:42px; padding:0 25px;" onclick="createCustomToken()">Forge Token</button>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Token Signature</th>
                                <th>Config (Users / Session)</th>
                                <th>Active Logins</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="tokensTableBody">
                            <tr><td colspan="5"><div class="loader"></div></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-health" class="tab-content">
                <div class="header">
                    <h1>Private Server Vitals</h1>
                </div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:20px;">
                    <div style="background:var(--card); padding:25px; border-radius:12px; border:1px solid var(--border);">
                        <h3 style="color:#8b949e; font-size:12px; text-transform:uppercase; margin-bottom:10px;">Traffic Analyzer Engine</h3>
                        <div style="font-size:24px; font-weight:bold; color:#fff; margin-bottom:5px;" id="h-uptime">Fetching...</div>
                        <p style="color:var(--success); font-size:13px;">✔ Server is fully operational</p>
                    </div>
                    <div style="background:var(--card); padding:25px; border-radius:12px; border:1px solid var(--border);">
                        <h3 style="color:#8b949e; font-size:12px; text-transform:uppercase; margin-bottom:10px;">Security Status</h3>
                        <div style="font-size:18px; font-weight:bold; color:var(--accent); margin-bottom:5px;">Military-Grade Honeypot: ACTIVE</div>
                        <p style="color:#8b949e; font-size:13px;">IP Rate Limiting & Auto-Bans are protecting the Node.</p>
                    </div>
                </div>
                <p style="color:var(--warn); margin-top:30px; font-size:13px; background:rgba(210,153,34,0.1); padding:15px; border-radius:8px; border:1px solid rgba(210,153,34,0.3);">
                    ⚠️ <b>Architect Note:</b> Deep traffic analysis (GeoIP, Hit counters per file) requires a Time-Series Database (like Redis). Tracking every hit on JSON files will cause race conditions and server crashes. The current setup is optimized for ultra-fast media streaming.
                </p>
            </div>

        </div>
    </div>

    <script>
        let allFiles = [];
        let selectedSlugs = new Set();
        const FALLBACK_THUMB = "https://qlynk.vercel.app/Quicklink-Banner.png";

        // --- TAB LOGIC ---
        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            btnElement.classList.add('active');
            
            if(tabId === 'tokens') fetchTokens();
            if(tabId === 'files') fetchFiles();
            if(tabId === 'health') fetchHealth();
        }

        // --- UNIVERSAL PREVIEW ENGINE ---
        async function openPreview(slug, mime, title) {
            const modal = document.getElementById('previewModal');
            const body = document.getElementById('previewBody');
            document.getElementById('previewTitle').innerText = title;
            
            modal.classList.add('show');
            body.innerHTML = '<div class="loader"></div>';
            
            const url = `/f/${slug}`;
            
            setTimeout(async () => {
                if(mime.startsWith('video')) {
                    body.innerHTML = `<video src="${url}" class="preview-video" controls autoplay playsinline></video>`;
                } else if(mime.startsWith('audio')) {
                    body.innerHTML = `<div style="text-align:center; padding:50px;"><img src="${FALLBACK_THUMB}" style="width:200px; border-radius:50%; margin-bottom:20px; box-shadow:0 0 30px var(--accent);"><br><audio src="${url}" controls autoplay style="width:100%; max-width:400px;"></audio></div>`;
                } else if(mime.startsWith('image')) {
                    body.innerHTML = `<img src="${url}" class="preview-img">`;
                } else {
                    // Treat as text/code
                    try {
                        const res = await fetch(url);
                        const text = await res.text();
                        // Sanitize html
                        const cleanText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                        body.innerHTML = `<pre class="preview-code"><code>${cleanText}</code></pre>`;
                    } catch(e) {
                        body.innerHTML = `<div style="color:var(--danger); padding:20px;">Cannot preview this binary/external file directly.</div>`;
                    }
                }
            }, 500);
        }

        function closePreview() {
            const modal = document.getElementById('previewModal');
            const body = document.getElementById('previewBody');
            modal.classList.remove('show');
            // Destroy media element to stop audio/video
            body.innerHTML = ''; 
        }

        // --- FILES TAB LOGIC ---
        function formatBytes(bytes) {
            if(bytes === 0) return '0 B';
            const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        async function fetchFiles() {
            try {
                const res = await fetch('/api/history');
                allFiles = await res.json();
                document.getElementById('total-files-count').innerText = `${allFiles.length} Total Assets`;
                renderFilesTable();
            } catch(e) {
                document.getElementById('filesTableBody').innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--danger);">Connection Error</td></tr>`;
            }
        }

        function renderFilesTable() {
            const tbody = document.getElementById('filesTableBody');
            tbody.innerHTML = '';
            
            if(allFiles.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#8b949e;">Vault is empty.</td></tr>`;
                return;
            }

            allFiles.forEach(f => {
                const isVideo = f.mime_type.startsWith('video');
                const badge = f.is_external ? `<span class="badge b-ext">External</span>` : 
                             (isVideo ? `<span class="badge b-vid">Video</span>` : `<span class="badge b-doc">Document</span>`);
                
                const isChecked = selectedSlugs.has(f.slug) ? 'checked' : '';
                const thumbImg = f.thumbnail && f.thumbnail.startsWith('/f/') ? f.thumbnail : FALLBACK_THUMB;
                
                // Escape quotes for JS inline functions
                const safeTitle = f.title.replace(/'/g, "\\'").replace(/"/g, "&quot;");
                
                tbody.innerHTML += `
                    <tr>
                        <td><input type="checkbox" class="file-chk" value="${f.slug}" ${isChecked} onchange="toggleSelection('${f.slug}', this.checked)"></td>
                        <td><img src="${thumbImg}" class="row-thumb" onclick="openPreview('${f.slug}', '${f.mime_type}', '${safeTitle}')" onerror="this.src='${FALLBACK_THUMB}'" title="Click to Preview"></td>
                        <td><div style="font-weight:600; color:#fff; display:-webkit-box; -webkit-line-clamp:1; overflow:hidden;">${f.title}</div><div style="font-size:11px; color:#8b949e; margin-top:4px;">${f.slug}</div></td>
                        <td>${formatBytes(f.size_bytes)}</td>
                        <td>${badge}</td>
                        <td style="color:#8b949e;">${f.uploaded_at.substring(0,10)}</td>
                    </tr>
                `;
            });
            updateActionBar();
        }

        function toggleSelection(slug, isChecked) {
            if(isChecked) selectedSlugs.add(slug);
            else selectedSlugs.delete(slug);
            updateActionBar();
        }

        function toggleAll(chkElement) {
            document.querySelectorAll('.file-chk').forEach(chk => {
                chk.checked = chkElement.checked;
                toggleSelection(chk.value, chkElement.checked);
            });
        }

        function updateActionBar() {
            const bar = document.getElementById('actionBar');
            if(selectedSlugs.size > 0) {
                bar.classList.add('show');
                document.getElementById('selectedCount').innerText = `⚠️ ${selectedSlugs.size} files selected for permanent deletion`;
            } else {
                bar.classList.remove('show');
                document.getElementById('selectAll').checked = false;
            }
        }

        async function executeBulkDelete() {
            if(!confirm(`Are you absolutely sure you want to PERMANENTLY delete ${selectedSlugs.size} files?`)) return;
            try {
                const res = await fetch('/api/admin/bulk_delete', {
                    method: 'DELETE', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({slugs: Array.from(selectedSlugs)})
                });
                const data = await res.json();
                alert(data.message);
                selectedSlugs.clear();
                fetchFiles();
            } catch(e) { alert("Deletion failed. Check logs."); }
        }

        // --- TOKENS TAB LOGIC ---
        async function fetchTokens() {
            try {
                const res = await fetch('/api/admin/tokens');
                const data = await res.json();
                const tokensObj = data.tokens || {};
                const tbody = document.getElementById('tokensTableBody');
                tbody.innerHTML = '';
                
                const tokenKeys = Object.keys(tokensObj);
                if(tokenKeys.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#8b949e;">No tokens generated yet.</td></tr>`;
                    return;
                }

                const now = Date.now() / 1000;

                tokenKeys.sort((a,b) => tokensObj[b].created_at.localeCompare(tokensObj[a].created_at)).forEach(key => {
                    const t = tokensObj[key];
                    const isExpired = t.expires_at < now || t.status === 'expired';
                    const statusBadge = isExpired ? `<span class="badge b-ext">Expired</span>` : `<span class="badge b-vid">Active</span>`;
                    
                    const maxU = t.config ? t.config.max_users : '∞';
                    const sDays = t.config ? t.config.session_days : '1';
                    const activeLogins = t.active_sessions || 0;
                    
                    tbody.innerHTML += `
                        <tr style="opacity: ${isExpired ? '0.5' : '1'};">
                            <td>
                                <div style="font-family:monospace; color:var(--accent); font-weight:bold; margin-bottom:4px;">${key.substring(0,8)}...${key.slice(-4)}</div>
                                <div style="font-size:11px; color:#8b949e;">${t.email || 'System'}</div>
                            </td>
                            <td style="font-size:12px; color:#c9d1d9;">Max: <b>${maxU}</b> Users<br>Sess: <b>${sDays}</b> Days</td>
                            <td style="font-weight:bold; color:var(--success);">${activeLogins} / ${maxU}</td>
                            <td>${statusBadge}<br><span style="font-size:10px; color:#8b949e;">Ends: ${new Date(t.expires_at * 1000).toISOString().substring(0,10)}</span></td>
                            <td>
                                <div style="display:flex; gap:8px;">
                                    <button class="icon-btn" title="Copy Token URL" onclick="copyToken('${key}')">📋</button>
                                    <button class="icon-btn" title="Clear Active Sessions (Force Logout)" onclick="revokeToken('${key}')">🧹</button>
                                    <button class="icon-btn" title="Delete Token Entirely" onclick="deleteToken('${key}')">🗑️</button>
                                </div>
                            </td>
                        </tr>
                    `;
                });
            } catch(e) {
                document.getElementById('tokensTableBody').innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--danger);">Connection Error</td></tr>`;
            }
        }

        async function createCustomToken() {
            const u = document.getElementById('tUsers').value;
            const h = document.getElementById('tHours').value;
            const d = document.getElementById('tDays').value;
            
            try {
                const res = await fetch('/api/admin/token/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({max_users: parseInt(u), valid_hours: parseInt(h), session_days: parseInt(d)})
                });
                if(res.ok) { alert("Forge Success! Token Created."); fetchTokens(); }
            } catch(e) { alert("Token Forge Failed."); }
        }

        function copyToken(key) {
            const url = window.location.origin + `/view?token=${key}`;
            navigator.clipboard.writeText(url);
            alert("Secure Token Link copied to clipboard!");
        }

        async function revokeToken(key) {
            if(!confirm("Clear all active sessions for this token? Users will be logged out instantly.")) return;
            try {
                const res = await fetch(`/api/admin/token/revoke/${key}`, {method: 'POST'});
                if(res.ok) { alert("Sessions cleared."); fetchTokens(); }
            } catch(e) { alert("Failed to clear sessions."); }
        }

        async function deleteToken(key) {
            if(!confirm("Delete this token entirely? It will be permanently removed.")) return;
            try {
                const res = await fetch(`/api/admin/token/${key}`, {method: 'DELETE'});
                if(res.ok) { alert("Token deleted."); fetchTokens(); }
            } catch(e) { alert("Failed to delete token."); }
        }

        // --- HEALTH TAB ---
        async function fetchHealth() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('h-uptime').innerText = data.formatted_total_size + " Vault Usage";
            } catch(e) {}
        }

        // Initialize First Tab
        fetchFiles();
    </script>
</body>
</html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard(request: Request, token: str = Depends(verify_auth)):
    return HTMLResponse(content=ADMIN_DASHBOARD_HTML)


# ==========================================
# 19. GLOBAL LOADER & REFINED CINEMATIC INTRO
# ==========================================
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse
from fastapi import Request

# Visual Styles and Core Animation Logic
GLOBAL_UI_INJECTION = """
<style>
    /* Fullscreen Overlay */
    #qlynk-global-loader {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: #000000; z-index: 2147483647;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        opacity: 1; transition: opacity 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .loader-content { text-align: center; }
    
    /* Cinematic Text Effects (FIXED: Perfectly Centered) */
    .cine-text {
        color: #ffffff; font-family: 'Inter', sans-serif;
        opacity: 0; transform: translateY(20px);
        transition: all 1s ease; position: absolute; width: 100%; left: 0;
        text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center;
    }
    .cine-text.active { opacity: 1; transform: translateY(0); }
    .cine-title { font-size: 2.8rem; font-weight: 800; letter-spacing: 6px; text-transform: uppercase; }
    .cine-sub { font-size: 1.1rem; color: #00ffff; margin-top: 10px; letter-spacing: 3px; opacity: 0.7; }

    /* The Spinner & Messages */
    .spinner-box { margin-top: 20px; display: none; flex-direction: column; align-items: center; }
    .spinner-box.visible { display: flex; }
    .spinner {
        width: 50px; height: 50px; border: 2px solid rgba(0, 255, 255, 0.1);
        border-top: 2px solid #00ffff; border-radius: 50%;
        animation: spin 0.8s linear infinite; box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
    }
    #loading-msg { color: #8b949e; font-size: 12px; margin-top: 15px; letter-spacing: 2px; text-transform: uppercase; }
    
    @keyframes spin { to { transform: rotate(360deg); } }
    body.locked { overflow: hidden !important; }
</style>

<div id="qlynk-global-loader">
    <div id="intro-1" class="cine-text">
        <div class="cine-title">QLYNK Nobe Server</div>
        <div class="cine-sub">an app by Deep</div>
    </div>
    <div id="intro-2" class="cine-text">
        <div class="cine-title" style="font-size: 2.2rem;">a Deep Dey Creation</div>
        <div class="cine-sub">an Deep Dey Product</div>
    </div>

    <div id="loader-ui" class="spinner-box">
        <div class="spinner"></div>
        <div id="loading-msg">INITIALIZING SYSTEM...</div>
    </div>
</div>

<script>
    const messages = [
        "Waking up QLYNK Node...",
        "Syncing with Hugging Face Vault...",
        "Verifying Encryption Keys...",
        "Fetching Database History...",
        "Securing Data Stream...",
        "Finalizing Handshake..."
    ];

    document.addEventListener("DOMContentLoaded", () => {
        const overlay = document.getElementById("qlynk-global-loader");
        const i1 = document.getElementById("intro-1");
        const i2 = document.getElementById("intro-2");
        const loaderUI = document.getElementById("loader-ui");
        const msgEl = document.getElementById("loading-msg");
        
        document.body.classList.add("locked");
        
        // Check if we should play the full cinema or just the loader
        const path = window.location.pathname;
        const played = sessionStorage.getItem("intro_played");
        const showCinema = (path === "/" || path === "/dashboard" || path === "/view") && !played;

        let delay = 3500; // Base loading time

        if (showCinema) {
            delay = 10000; // Longer for cinema
            setTimeout(() => i1.classList.add("active"), 500);
            setTimeout(() => i1.classList.remove("active"), 3500);
            setTimeout(() => i2.classList.add("active"), 4500);
            setTimeout(() => i2.classList.remove("active"), 7500);
            setTimeout(() => {
                loaderUI.classList.add("visible");
                sessionStorage.setItem("intro_played", "true");
            }, 8000);
        } else {
            // Just show the loader for 3-5s
            loaderUI.classList.add("visible");
            let msgIdx = 0;
            const msgInterval = setInterval(() => {
                msgIdx = (msgIdx + 1) % messages.length;
                msgEl.innerText = messages[msgIdx];
            }, 800);
            setTimeout(() => clearInterval(msgInterval), 4000);
        }

        // Final Reveal
        setTimeout(() => {
            overlay.style.opacity = "0";
            setTimeout(() => {
                overlay.style.display = "none";
                document.body.classList.remove("locked");
            }, 800);
        }, delay);
    });
</script>
"""

class GlobalLoaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Inject into ALL HTML responses for a consistent brand feel
        if response.headers.get("content-type", "").startswith("text/html"):
            body_iterator = response.body_iterator
            body_bytes = [section async for section in body_iterator]
            body_bytes = b"".join(body_bytes)
            html_content = body_bytes.decode("utf-8")
            
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", GLOBAL_UI_INJECTION + "\\n</body>")
            else:
                html_content += GLOBAL_UI_INJECTION
                
            headers = dict(response.headers)
            if "content-length" in headers:
                del headers["content-length"] 
                
            return HTMLResponse(content=html_content, status_code=response.status_code, headers=headers)
        return response

app.add_middleware(GlobalLoaderMiddleware)

# ==========================================
# 20. ENTERPRISE GARBAGE COLLECTION (TEMP SWEEPER)
# ==========================================
import time as time_module

async def auto_garbage_collector():
    """Background loop to clean /tmp folder and free up RAM/Disk"""
    logger.info("🧹 Garbage Collector Initiated. Sweeping every 6 hours.")
    await asyncio.sleep(300) # Wait 5 mins on boot before first sweep
    
    while True:
        try:
            tmp_dir = "/tmp"
            if os.path.exists(tmp_dir):
                current_time = time_module.time()
                deleted_count = 0
                
                for filename in os.listdir(tmp_dir):
                    file_path = os.path.join(tmp_dir, filename)
                    # Delete files older than 6 hours
                    if os.path.isfile(file_path) and (current_time - os.path.getmtime(file_path)) > 21600:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except:
                            pass
                
                if deleted_count > 0:
                    logger.info(f"🧹 Garbage Collection complete: {deleted_count} ghost files deleted from /tmp")
        except Exception as e:
            logger.error(f"Garbage Collector Error: {e}")
            
        await asyncio.sleep(21600) # Sleep for 6 hours

# Add background task dynamically using startup event
@app.on_event("startup")
async def start_garbage_collector():
    asyncio.create_task(auto_garbage_collector())


# ==========================================
# 21. THE "LUCKY 21" SECRET TERMINAL (ARCHITECT EASTER EGG)
# ==========================================
@app.get("/21", response_class=HTMLResponse)
async def lucky_21_easter_egg():
    """The Secret Route: Deep Dey's Matrix Terminal"""
    lucky_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terminal 21 - Deep Dey</title>
        <style>
            body { 
                background-color: #000; color: #0f0; 
                font-family: 'Courier New', Courier, monospace; 
                padding: 40px; margin: 0; overflow: hidden;
            }
            .glow { text-shadow: 0 0 10px #0f0, 0 0 20px #0f0; }
            #cursor { animation: blink 1s step-end infinite; }
            @keyframes blink { 50% { opacity: 0; } }
            .matrix-text { white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
        </style>
    </head>
    <body>
        <div id="console" class="matrix-text glow"></div>
        <span id="cursor">█</span>

        <script>
            const text = `
SYSTEM BOOT SEQUENCE INITIATED...
[OK] Core Node Mounted.
[OK] Cryptographic Shields Online.
[OK] Routing via Hugging Face Vault.

>>> IDENTIFYING CREATOR...
>>> MATCH FOUND: DEEP DEY (The Architect)

Congratulations. You found Route 21.
This node is operating at maximum capacity.
No limits. No boundaries. Just pure logic.

"I can only show you the door, you're the one that has to walk through it."

>>> Connection Secure. Node is Alive.
            `;
            
            let i = 0;
            const speed = 30; // Typing speed in ms
            const consoleEl = document.getElementById("console");
            
            function typeWriter() {
                if (i < text.length) {
                    consoleEl.innerHTML += text.charAt(i);
                    i++;
                    setTimeout(typeWriter, speed);
                }
            }
            
            setTimeout(typeWriter, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=lucky_html)
# ==========================================
# 22. QLYNK-TIFY (ENTERPRISE HYBRID MUSIC ENGINE) - V6 TITAN
# ==========================================
import urllib.parse
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, Response
from fastapi import Request, Depends, HTTPException
import io
import re
import asyncio
import uuid
import time
import json
import os
import random
from typing import Dict, Any

# --- 1. Qlynktify Aggressive Metadata Cleaners ---
def clean_music_title(raw_filename: str) -> dict:
    """Aggressive Regex Engine to purify pirated/messy audio filenames"""
    name = os.path.splitext(raw_filename)[0]
    
    garbage_patterns = [
        r"\(official.*?\)", r"\[.*?\]", r"\(lyric.*?\)", r"official video", 
        r"audio", r"128kbps", r"320kbps", r"64kbps", r"music video", r"hq", r"hd", r"4k",
        r"-?\s*pagalworld(\.com|\.nl|\.io)?\s*-?", r"-?\s*mrjatt(\.com)?\s*-?", 
        r"-?\s*djpunjab(\.com)?\s*-?", r"-?\s*pendujatt\s*-?", r"-?\s*djmaza\s*-?",
        r"song download", r"mp3 download", r"free download", r"djmaza", r"wapking",
        r"\(.*?\)", r"\[.*?\]", r"www\..*?\.com", r"-\s*Copy"
    ]
    for pattern in garbage_patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        
    name = name.replace("_", " ").strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'^-\s*|\s*-$', '', name).strip()
    
    parts = name.split(" - ", 1)
    if len(parts) == 2:
        return {"artist": parts[0].strip(), "title": parts[1].strip(), "clean_full": f"{parts[0].strip()} {parts[1].strip()}"}
    return {"artist": "Unknown Artist", "title": name, "clean_full": name}

# --- 2. Advanced Cache & Batch Managers (Zero API Spam) ---
# We maintain RAM states and sync to Hugging Face only every few minutes.
def get_qlynktify_meta_db() -> Dict[str, Any]:
    if DB_CACHE.get("qlynktify_meta", {}).get("data") is None:
        try:
            file_path = hf_hub_download(repo_id=DATASET_REPO, filename="qlynktify_meta.json", repo_type="dataset", token=HF_TOKEN)
            with open(file_path, "r") as f:
                data = json.load(f)
            DB_CACHE.setdefault("qlynktify_meta", {})["data"] = data
            DB_CACHE["qlynktify_meta"]["last_sync"] = time.time()
        except Exception:
            empty_db = {"tracks": {}, "play_counts": {}}
            DB_CACHE.setdefault("qlynktify_meta", {})["data"] = empty_db
            return empty_db
    return DB_CACHE["qlynktify_meta"]["data"]

def sync_qlynktify_meta_to_cloud():
    """Background task to sync metadata and play counts without blocking UI"""
    db_data = DB_CACHE.get("qlynktify_meta", {}).get("data")
    if not db_data: return
    
    # Only sync if it's been more than 5 mins to prevent API limits
    if time.time() - DB_CACHE.get("qlynktify_meta", {}).get("last_sync", 0) < 300:
        return 
        
    with open("qlynktify_meta.json", "w") as f:
        json.dump(db_data, f, indent=4)
    try:
        api.upload_file(path_or_fileobj="qlynktify_meta.json", path_in_repo="qlynktify_meta.json", repo_id=DATASET_REPO, repo_type="dataset")
        DB_CACHE["qlynktify_meta"]["last_sync"] = time.time()
        logger.info("Qlynktify Cloud Sync Complete.")
    except Exception as e:
        logger.warning(f"Cloud Sync failed: {e}")

# --- 3. Dynamic RAM Stream Tokens ---
qlynktify_stream_tokens = {}

# --- 4. FastAPI Endpoints (The Core Engine) ---
@app.get("/api/qlynktify/library")
async def fetch_qlynktify_library(access: dict = Depends(verify_view_access)):
    try:
        db = get_db()
        meta_db = get_qlynktify_meta_db()
        music_files = []
        
        play_counts = meta_db.get("play_counts", {})
        
        for f in db.get("files", []):
            if str(f.get("mime_type", "")).startswith("audio/"):
                cleaned_data = clean_music_title(f.get("filename", ""))
                f["clean_title"] = cleaned_data["title"]
                f["artist_guess"] = cleaned_data["artist"]
                f["search_query"] = cleaned_data["clean_full"]
                f["track_id"] = f.get("slug")
                f["play_count"] = play_counts.get(f.get("slug"), 0)
                music_files.append(f)
                
        sorted_tracks = sorted(music_files, key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return {"status": "success", "tracks": sorted_tracks}
    except Exception as e:
        logger.error(f"Library Fetch Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load Vault Database")

@app.post("/api/qlynktify/increment_play/{slug}")
async def increment_play_count(slug: str, access: dict = Depends(verify_view_access)):
    """Increments the play count of a track locally, queues cloud sync"""
    meta_db = get_qlynktify_meta_db()
    if "play_counts" not in meta_db:
        meta_db["play_counts"] = {}
        
    current_count = meta_db["play_counts"].get(slug, 0)
    meta_db["play_counts"][slug] = current_count + 1
    
    # Trigger background sync (won't actually upload unless 5 mins passed)
    asyncio.create_task(asyncio.to_thread(sync_qlynktify_meta_to_cloud))
    return {"status": "success", "new_count": meta_db["play_counts"][slug]}

@app.get("/api/qlynktify/meta")
async def get_track_metadata(q: str, access: dict = Depends(verify_view_access)):
    """iTunes API Bypass + internal Fallback Engine"""
    import aiohttp
    meta_db = get_qlynktify_meta_db()
    query_key = q.lower().strip()
    
    # 1. Check if already cached
    if query_key in meta_db.get("tracks", {}):
        return meta_db["tracks"][query_key]

    result = {"artist": "Unknown Artist", "album": "Vault Single", "artwork": "", "real_title": ""}
    
    try:
        # 🛡️ Bypass Header: iTunes needs this to not return 403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(q)}&entity=song&limit=1"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("resultCount", 0) > 0:
                        track = data["results"][0]
                        result = {
                            "artist": track.get("artistName", "Unknown Artist"),
                            "album": track.get("collectionName", "Unknown Album"),
                            "artwork": track.get("artworkUrl100", "").replace("100x100bb", "600x600bb"),
                            "real_title": track.get("trackName", "")
                        }
    except Exception as e:
        logger.warning(f"iTunes API Error: {e}")

    # 🔄 FALLBACK: Agar iTunes fail hua, history/vault se thumbnail lo
    if not result["artwork"]:
        db = get_db()
        # Find match in database for this query
        for f in db.get("files", []):
            if q.lower() in f.get("filename", "").lower() or q.lower() in f.get("title", "").lower():
                if f.get("thumbnail"):
                    result["artwork"] = f["thumbnail"]
                    result["album"] = "Archived Asset"
                    break

    meta_db.setdefault("tracks", {})[query_key] = result
    asyncio.create_task(asyncio.to_thread(sync_qlynktify_meta_to_cloud))
    return result

@app.get("/api/qlynktify/lyrics")
async def get_track_lyrics(q: str, access: dict = Depends(verify_view_access)):
    import aiohttp
    try:
        url = f"https://lrclib.net/api/search?track_name={urllib.parse.quote(q)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if len(data) > 0:
                        return {"synced": data[0].get("syncedLyrics"), "plain": data[0].get("plainLyrics")}
    except Exception:
        pass
    return {"synced": None, "plain": None}

@app.get("/api/qlynktify/generate_stream/{slug}")
async def generate_music_stream(slug: str, access: dict = Depends(verify_view_access)):
    # 5 MINUTE TOKEN EXPIRY
    stream_token = uuid.uuid4().hex
    qlynktify_stream_tokens[stream_token] = {
        "slug": slug,
        "expires": time.time() + 300 
    }
    return {"stream_token": stream_token}

@app.get("/stream/audio/qlynktify/{token}")
async def ram_buffered_audio_stream(token: str, request: Request):
    """The Ultimate 30-Sec Chunk Engine & Anti-Piracy Shield"""
    
    # 🛡️ THE SHIELD: Block Direct URL hits from Network Tab
    fetch_dest = request.headers.get("sec-fetch-dest", "")
    if fetch_dest == "document" or not fetch_dest:
        return Response(content=b"405 Method Not Allowed - Piracy Shield Active.", status_code=405)

    session = qlynktify_stream_tokens.get(token)
    if not session or time.time() > session["expires"]:
        return Response(content=b"TOKEN_EXPIRED_OR_INVALID", status_code=403)
        
    db = get_db()
    file_record = next((f for f in db.get("files", []) if f["slug"] == session["slug"]), None)
    if not file_record:
        raise HTTPException(status_code=404, detail="Track not found.")

    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename=file_record["path"], repo_type="dataset", token=HF_TOKEN)
    except Exception as e:
        return Response(content=b"INTERNAL_VAULT_ERROR", status_code=500)
    
    range_header = request.headers.get("Range", 0)
    file_size = os.path.getsize(file_path)
    
    # 🛡️ RAM OPTIMIZATION: Max chunk size 512KB (approx 30 secs)
    MAX_CHUNK = 1024 * 512 
    
    start = 0
    end = file_size - 1
    status_code = 200
    
    if range_header:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        if len(byte_range) > 1 and byte_range[1]:
            end = int(byte_range[1])
        status_code = 206
        
    # Cap the requested range to our max 30-second chunk
    if (end - start + 1) > MAX_CHUNK:
        end = start + MAX_CHUNK - 1
        
    chunk_size = (end - start) + 1
    
    def file_chunk_generator():
        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_read = 0
                while bytes_read < chunk_size:
                    read_size = min(1024 * 128, chunk_size - bytes_read)
                    chunk = f.read(read_size)
                    if not chunk: break
                    bytes_read += len(chunk)
                    yield chunk
        except Exception as e:
            pass

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": file_record.get("mime_type", "audio/mpeg"),
        "Cache-Control": "no-store", 
        "Access-Control-Allow-Origin": "*"
    }
    
    return StreamingResponse(file_chunk_generator(), status_code=status_code, headers=headers)

# ==========================================
# 5. RAW HTML FRONTEND PAYLOAD
# ==========================================
QLYNKTIFY_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Qlynk-tify | App Engine V6</title>
    <link rel="icon" type="image/png" href="https://qlynk.vercel.app/quicklink-logo.png">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jsmediatags/3.9.5/jsmediatags.min.js"></script>

<style>
        /* === CORE VARIABLES === */
        @import url('https://fonts.googleapis.com/css2?family=Circular+Std:wght@400;700;900&display=swap');
        :root {
            --bg-base: #000000; --bg-highlight: #121212; --bg-elevated: #1a1a1a; --bg-hover: #2a2a2a;
            --accent: #1ed760; --accent-hover: #1fdf64; --qlynk-accent: #bc8cff;
            --text-base: #b3b3b3; --text-bright: #ffffff; --text-dim: #6a6a6a;
            --font-family: 'Circular Std', -apple-system, sans-serif;
            --dom-color: #121212; --dom-color-dim: rgba(18,18,18,0.1);
            --trans: all 0.2s ease;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: var(--font-family); outline: none; }
        body { background: var(--bg-base); color: var(--text-bright); display: flex; flex-direction: column; height: 100vh; overflow: hidden; user-select: none; -webkit-user-select: none;}
        
        /* === UTILS & FORMS === */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background-color: rgba(255,255,255,0.2); border-radius: 4px;}
        ::-webkit-scrollbar-thumb:hover { background-color: rgba(255,255,255,0.4); }
        
        .btn-icon { background: transparent; border: none; color: var(--text-base); cursor: pointer; border-radius: 50%; padding: 6px; display: flex; align-items: center; justify-content: center; transition: var(--trans); }
        .btn-icon:hover { color: var(--text-bright); background: rgba(255,255,255,0.1); }
        
        .input-base { width: 100%; padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: #fff; font-size: 14px; margin-bottom: 15px;}
        .input-base:focus { border-color: var(--qlynk-accent); }
        .btn-solid { background: var(--text-bright); color: #000; font-weight: 700; padding: 12px 24px; border-radius: 24px; border: none; cursor: pointer; transition: var(--trans); width: 100%; display:flex; justify-content:center; align-items:center; text-decoration:none;}
        .btn-solid:hover { transform: scale(1.02); }

        /* === MODALS & TOASTS === */
        .overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.8); z-index: 99999; display: none; justify-content: center; align-items: center; backdrop-filter: blur(5px);}
        .modal { background: var(--bg-elevated); padding: 30px; border-radius: 12px; width: 350px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
        .modal-title { font-size: 20px; font-weight: 900; margin-bottom: 20px; }
        
        .toast { position: fixed; bottom: -50px; left: 50%; transform: translateX(-50%); background: var(--qlynk-accent); color: #000; padding: 12px 24px; border-radius: 30px; font-weight: 900; font-size: 14px; z-index: 100000; transition: bottom 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); box-shadow: 0 10px 20px rgba(188, 140, 255, 0.3);}
        .toast.show { bottom: 120px; }

        /* === APP CONTEXT MENU === */
        .context-menu { position: fixed; background: #282828; border-radius: 6px; box-shadow: 0 16px 24px rgba(0,0,0,0.8); padding: 4px; z-index: 99999; display: none; min-width: 220px; border: 1px solid rgba(255,255,255,0.1);}
        .context-menu.active { display: block; animation: popIn 0.1s; transform-origin: top left;}
        .cm-item { padding: 10px 14px; color: #fff; font-size: 13px; font-weight: 500; cursor: pointer; border-radius: 4px; display: flex; align-items: center; gap: 12px; transition: var(--trans);}
        .cm-item:hover { background: rgba(255,255,255,0.1); color: var(--qlynk-accent);}
        @keyframes popIn { from {opacity:0; transform:scale(0.95);} to {opacity:1; transform:scale(1);} }

        /* === LAYOUT === */
        .app-wrapper { display: flex; flex: 1; overflow: hidden; padding: 8px; gap: 8px; }
        
        /* === SIDEBAR === */
        .sidebar { width: 280px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; height: calc(100vh - 100px); /* Leave room for player */ }
        .sidebar-box { background: var(--bg-highlight); border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .nav-link { color: var(--text-base); text-decoration: none; font-weight: 700; font-size: 15px; display: flex; align-items: center; gap: 16px; cursor: pointer; transition: var(--trans); }
        .nav-link:hover, .nav-link.active { color: var(--text-bright); }
        .nav-link svg { width: 24px; height: 24px; fill: currentColor; }
        
        .lib-header { display: flex; justify-content: space-between; align-items: center; color: var(--text-base); font-weight: 700; margin-bottom: 5px; font-size: 14px;}
        .lib-list { display: flex; flex-direction: column; gap: 4px; }
        .lib-item { padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 14px; color: var(--text-base); transition: var(--trans); display: flex; align-items: center; gap: 12px; justify-content: space-between;}
        .lib-item:hover { background: rgba(255,255,255,0.05); color: #fff;}
        .lib-item.active { background: rgba(255,255,255,0.1); color: var(--accent);}
        
        .item-icon-box { display:flex; align-items:center; gap:12px; overflow:hidden;}
        .item-icon-wrap { width: 32px; height: 32px; border-radius: 4px; overflow: hidden; display:flex; justify-content:center; align-items:center; background:#282828; flex-shrink:0;}
        .item-icon-wrap img { width:100%; height:100%; object-fit:cover;}
        .item-icon-wrap svg { width: 16px; fill: #fff;}
        .item-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex:1;}
        
        /* === MAIN VIEW === */
        .main-view { flex: 1; background: linear-gradient(180deg, var(--dom-color) 0%, var(--bg-highlight) 40%, var(--bg-base) 100%); border-radius: 8px; overflow-y: auto; position: relative; transition: background 1s ease; display: flex; flex-direction: column;}
        .main-header { position: sticky; top: 0; padding: 12px 24px; background: rgba(0,0,0,0.5); backdrop-filter: blur(20px); z-index: 10; display: flex; justify-content: space-between; align-items: center;}
        .content-padding { padding: 24px; padding-bottom: 120px; flex: 1;}
        
        .hero-banner { display:flex; align-items:flex-end; gap:24px; margin-bottom:30px; padding-top:20px;}
        .hero-img { width: 180px; height: 180px; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); object-fit: cover;}
        .hero-info { display:flex; flex-direction:column; gap:8px;}
        .hero-type { font-size:12px; font-weight:700; text-transform:uppercase;}
        .hero-title { font-size:64px; font-weight:900; letter-spacing:-2px; line-height:1;}
        .hero-stats { font-size:14px; color:var(--text-base); font-weight:500;}

        /* === CARDS === */
        .section-title { font-size: 22px; font-weight: 900; margin: 30px 0 15px 0;}
        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 20px;}
        .music-card { background: var(--bg-elevated); padding: 16px; border-radius: 8px; cursor: pointer; transition: var(--trans); position: relative;}
        .music-card:hover { background: var(--bg-hover); }
        .mc-img-wrap { width: 100%; aspect-ratio: 1; border-radius: 6px; overflow: hidden; margin-bottom: 15px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); position: relative; background:#282828; display:flex; justify-content:center; align-items:center;}
        .mc-img { width: 100%; height: 100%; object-fit: cover; }
        .mc-play-btn { position: absolute; bottom: 8px; right: 8px; width: 44px; height: 44px; background: var(--accent); border-radius: 50%; display: flex; justify-content: center; align-items: center; color: #000; opacity: 0; transform: translateY(10px); transition: all 0.3s; box-shadow: 0 8px 15px rgba(0,0,0,0.3);}
        .music-card:hover .mc-play-btn { opacity: 1; transform: translateY(0); }
        .mc-play-btn:hover { transform: scale(1.05) !important; background: var(--accent-hover); }
        .mc-title { font-weight: 700; font-size: 15px; color: #fff; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        .mc-desc { font-size: 13px; color: var(--text-base); display:-webkit-box; -webkit-line-clamp:2; overflow:hidden;}

        /* === TRACK LIST TABLE === */
        .track-list { width: 100%; border-collapse: collapse; text-align: left; }
        .track-list th { color: var(--text-base); font-size: 12px; text-transform: uppercase; letter-spacing: 1px; padding: 10px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); font-weight: 400;}
        .track-row { cursor: pointer; border-radius: 4px; transition: var(--trans); }
        .track-row:hover { background: rgba(255,255,255,0.1); }
        .track-row td { padding: 8px 16px; vertical-align: middle; border-bottom: 1px solid transparent;}
        .track-row.playing { background: rgba(188, 140, 255, 0.15); }
        .track-row.playing .t-title { color: var(--qlynk-accent); }
        .t-img { width: 40px; height: 40px; border-radius: 4px; object-fit: cover;}
        .t-title { font-weight: 700; color: var(--text-bright); font-size: 15px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        .t-artist { color: var(--text-base); font-size: 13px;}
        
        .badge { font-size: 9px; padding: 2px 6px; border-radius: 12px; font-weight: 900; margin-left: 8px; text-transform: uppercase; vertical-align: middle;}
        .bg-local { background: var(--qlynk-accent); color: #000; }
        .bg-offline { background: var(--accent); color: #000; }

        /* === RIGHT PANEL (DUAL ENGINE) === */
        .right-panel { width: 320px; background: var(--bg-highlight); border-radius: 8px; padding: 20px; display: none; flex-direction: column; flex-shrink: 0; position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
        .right-panel.active { display: flex; animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
        
        .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; font-weight: 700; font-size: 14px;}
        .panel-toggle { display: flex; background: rgba(255,255,255,0.1); border-radius: 20px; padding: 2px;}
        .pt-btn { padding: 6px 14px; font-size: 12px; font-weight: bold; border: none; background: transparent; color: var(--text-base); cursor: pointer; border-radius: 18px; transition: var(--trans);}
        .pt-btn.active { background: var(--text-bright); color: #000; }
        
        .rp-img-wrap { width: 100%; aspect-ratio: 1; border-radius: 8px; overflow: hidden; margin-bottom: 15px; box-shadow: 0 15px 30px rgba(0,0,0,0.5);}
        .rp-img-wrap img { width: 100%; height: 100%; object-fit: cover;}
        
        /* Lyrics & Visualizer */
        .lyrics-container { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; font-size: 22px; font-weight: 900; line-height: 1.3; scroll-behavior: smooth; padding-right: 10px; padding-bottom: 30px;}
        .lyric-line { color: rgba(255,255,255,0.3); transition: var(--trans); cursor: pointer; transform-origin: left center;}
        .lyric-line:hover { color: rgba(255,255,255,0.8); }
        .lyric-line.active { color: var(--text-bright); transform: scale(1.05); text-shadow: 0 0 15px rgba(255,255,255,0.2); }
        
        /* 🔥 Visualizer Glow Update */
        .visualizer-container { 
            flex: 1; 
            display: none; 
            justify-content: center; 
            align-items: center; 
            background: radial-gradient(circle, var(--dom-color-dim) 0%, transparent 80%); 
            border-radius: 8px;
            box-shadow: inset 0 0 50px var(--dom-color-dim);
            border: 1px solid rgba(255,255,255,0.05);
            transition: all 1s ease;
        }
        #canvasVisualizer { width: 100%; height: 100%; filter: drop-shadow(0 0 15px var(--dom-color)); }

        /* === BOTTOM PLAYER BAR === */
        .player-bar { 
            height: 95px; 
            background: #000000; 
            border-top: 1px solid #282828; 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            padding: 0 20px; 
            z-index: 9999 !important; /* Force to top */
            position: fixed;
            bottom: 0;
            width: 100%;
        }
        .p-left, .p-right { width: 30%; min-width: 200px; display: flex; align-items: center; }
        .p-center { width: 40%; max-width: 722px; display: flex; flex-direction: column; align-items: center; gap: 8px; }
        
        .np-img { width: 56px; height: 56px; border-radius: 6px; object-fit: cover; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.5);}
        .np-info { margin-left: 14px; display: flex; flex-direction: column; justify-content: center; overflow:hidden;}
        .np-title { font-size: 14px; font-weight: 700; color: #fff; white-space: nowrap; text-overflow: ellipsis; overflow:hidden; display:flex; align-items:center; gap:8px;}
        .np-artist { font-size: 12px; color: var(--text-base); margin-top: 4px; white-space: nowrap;}
        
        .p-controls { display: flex; align-items: center; gap: 20px; visibility: visible !important; }
        .c-btn { background: transparent; border: none; color: var(--text-base); cursor: pointer; transition: 0.2s; position: relative; display:flex; align-items:center; justify-content:center;}
        .c-btn svg { width: 16px; height: 16px; fill: currentColor; }
        .c-btn:hover { color: var(--text-bright); transform: scale(1.1);}
        .c-btn.active { color: var(--accent); }
        .c-btn.active::after { content: ''; position: absolute; bottom: -6px; left: 50%; transform: translateX(-50%); width: 4px; height: 4px; background: var(--accent); border-radius: 50%;}
        
        .c-btn-play { background: var(--text-bright); color: #000; border-radius: 50%; width: 34px; height: 34px;}
        .c-btn-play svg { fill: #000; }
        .c-btn-play:hover { transform: scale(1.05); background: #fff; }
        
        .indicator-badge { position: absolute; top: -5px; right: -5px; background: var(--accent); color: #000; font-size: 8px; font-weight: 900; padding: 2px 4px; border-radius: 10px; display: none;}
        
        .progress-wrap { width: 100%; display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-base); font-weight: 700; font-variant-numeric: tabular-nums;}
        .prog-bg { flex: 1; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; cursor: pointer; position: relative; display: flex; align-items: center;}
        .prog-bg:hover .prog-thumb { opacity: 1; transform: scale(1); }
        .prog-bg:hover .prog-fill { background: var(--accent); }
        .prog-fill { height: 100%; background: #fff; border-radius: 2px; width: 0%; pointer-events: none;}
        .prog-thumb { width: 12px; height: 12px; background: #fff; border-radius: 50%; position: absolute; margin-left: -6px; opacity: 0; transform: scale(0); box-shadow: 0 2px 5px rgba(0,0,0,0.5); transition: var(--trans);}

        .vol-bg { width: 90px; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; cursor: pointer; position: relative; display: flex; align-items: center;}
        .vol-bg:hover .prog-fill { background: var(--accent); }
        .vol-bg:hover .prog-thumb { opacity: 1; transform: scale(1); }
        
        .loader-micro { width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.2); border-top: 2px solid var(--accent); border-radius: 50%; animation: spin 1s linear infinite; display: inline-block; margin-left:8px; vertical-align:middle;}
        @keyframes spin { 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <div id="toast" class="toast">Action Successful</div>

    
    <div class="overlay" id="plModal">
        <div class="modal">
            <div class="modal-title">Create Playlist</div>
            <input type="text" id="plNameInput" class="input-base" placeholder="My Awesome Playlist">
            
            <div style="display:flex; gap:10px;">
                <button class="btn-solid" style="background:transparent; color:#fff; border:1px solid #333;" onclick="document.getElementById('plModal').style.display='none'">Cancel</button>
                <button class="btn-solid" onclick="createPlaylistAction()">Create</button>
            </div>
        </div>
    </div>

    <div class="context-menu" id="contextMenu">
        <div class="cm-item" onclick="queueNext()"><svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M12.7 1a.7.7 0 0 0-.7.7v5.15L2.05 1.107A.7.7 0 0 0 1 1.712v12.575a.7.7 0 0 0 1.05.607L12 9.149V14.3a.7.7 0 0 0 1.4 0V1.7a.7.7 0 0 0-.7-.7z"/></svg> Play Next</div>
        <div class="cm-item" onclick="addToQueue()"><svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M14 11H2v-2h12v2zm0-4H2V5h12v2zM2 15h8v-2H2v2z"/></svg> Add to Queue</div>
        <hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:4px 0;">
        <div class="cm-item" onclick="showAddToPlaylistMenu()"><svg style="width:16px;" viewBox="0 0 24 24"><path fill="currentColor" d="M14 10H2v2h12v-2zm0-4H2v2h12V6zm4 8v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM2 16h8v-2H2v2z"/></svg> Add to Playlist</div>
        <div class="cm-item" onclick="saveToOfflineContext()"><svg style="width:16px;" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15l-4-4 1.41-1.41L11 14.17V7h2v7.17l2.59-2.59L17 13l-5 5z"/></svg> Save for Offline</div>
    </div>
    
    <div class="context-menu" id="plSubMenu">
        </div>

    <div class="context-menu" id="genericMenu">
        <div class="cm-item" onclick="location.reload()"><svg style="width:16px;" viewBox="0 0 24 24"><path fill="currentColor" d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg> Reload Engine</div>
    </div>

    <div class="app-wrapper">
        <div class="sidebar">
            <div class="sidebar-box" style="padding-bottom:10px;">
                <a class="nav-link active" onclick="renderHomeView()"><svg viewBox="0 0 24 24"><path d="M12 3l10 9h-3v8H5v-8H2l10-9zm-1 12h2v-4h-2v4z"/></svg> Home</a>
                <a class="nav-link" onclick="renderQueueView()"><svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg> Queue</a>
            </div>
            
            <div class="sidebar-box" style="flex: 1; overflow-y: auto; padding-top:10px;">
                <div class="lib-header">
                    <span style="display:flex; align-items:center; gap:8px;"><svg style="width:20px; fill:currentColor;" viewBox="0 0 24 24"><path d="M3 3h18v18H3V3zm16 16V5H5v14h14zM7 7h10v2H7V7zm0 4h10v2H7v-2zm0 4h7v2H7v-2z"/></svg> Playlists</span>
                    <button class="btn-icon" title="Create Playlist" onclick="document.getElementById('plModal').style.display='flex'"><svg style="width:18px;" viewBox="0 0 24 24"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg></button>
                </div>
                <div class="lib-list" id="sidebarPlaylists">
                    </div>
                
                <hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;">
                
                <div class="lib-header">
                    <span style="display:flex; align-items:center; gap:8px;"><svg style="width:20px; fill:currentColor;" viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg> Local Edge</span>
                    <button class="btn-icon" title="Add Folder" onclick="linkLocalFolder()"><svg style="width:18px;" viewBox="0 0 24 24"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg></button>
                </div>
                <div class="lib-list" id="sidebarLocalFolders">
                    <div style="font-size:12px; color:var(--text-dim); padding:0 10px;">No folders added.</div>
                </div>
            </div>
        </div>

        <div class="main-view" id="mainView">
            <div class="main-header">
                <div style="display:flex; gap:10px;">
                    <button class="btn-icon" style="background:rgba(0,0,0,0.7); width:32px; height:32px;" onclick="renderHomeView()">❮</button>
                    <button class="btn-icon" style="background:rgba(0,0,0,0.7); width:32px; height:32px;" onclick="renderQueueView()">❯</button>
                </div>
                <div style="width:36px; height:36px; border-radius:50%; background:var(--qlynk-accent); color:#000; display:flex; justify-content:center; align-items:center; font-weight:900;">Q</div>
            </div>

            <div class="content-padding" id="dynamicContent">
                <h1 style="font-size:40px; font-weight:900; margin-top:50px;">Initializing Qlynktify V6...</h1>
            </div>
        </div>

        <div class="right-panel" id="rightPanel">
            <div class="panel-header">
                <span>Now Playing</span>
                <div class="panel-toggle">
                    <button class="pt-btn active" onclick="switchRightPanel('lyrics')">Lyrics</button>
                    <button class="pt-btn" onclick="switchRightPanel('visuals')">Visuals</button>
                </div>
                <button class="btn-icon" onclick="toggleRightPanel()">✖</button>
            </div>
            
            <div class="rp-img-wrap"><img id="rp-cover" src="https://qlynk.vercel.app/quicklink-logo.png"></div>
            <div style="font-size:22px; font-weight:900; margin-bottom:4px;" id="rp-title">Not Playing</div>
            <div style="font-size:14px; color:var(--text-base); font-weight:700; margin-bottom:20px;" id="rp-artist">Qlynk Architecture</div>

            <div class="lyrics-container" id="lyricsContainer">
                <div style="text-align:center; color:var(--text-dim); font-size:14px; margin-top:50px;">Lyrics will appear here.</div>
            </div>
            
            <div class="visualizer-container" id="visualsContainer">
                <canvas id="canvasVisualizer"></canvas>
            </div>
        </div>
    </div>

    <div class="player-bar">
        <div class="p-left">
            <img src="https://qlynk.vercel.app/quicklink-logo.png" class="np-img" id="bp-cover" onclick="toggleRightPanel()">
            <div class="np-info">
                <div class="np-title">
                    <span id="bp-title" title="No Track Selected">No Track Selected</span>
                    <div class="loader-micro" id="blob-loader" style="display:none;"></div>
                </div>
                <div class="np-artist" id="bp-artist">Qlynk Node</div>
            </div>
        </div>
        
        <div class="p-center">
            <div class="p-controls">
                <button class="c-btn" id="btn-shuffle" onclick="toggleShuffle()">
                    <svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M13.151.922a.75.75 0 1 0-1.06 1.06L13.109 3H11.16a3.75 3.75 0 0 0-2.873 1.34l-6.173 7.356A2.25 2.25 0 0 1 .39 12.5H0v1.5h.39a3.75 3.75 0 0 0 2.873-1.34l6.173-7.356a2.25 2.25 0 0 1 1.724-.804h1.947l-1.017 1.018a.75.75 0 0 0 1.06 1.06L15.98 4.5l-2.83-3.578zM.39 3.5H0V2h.39a3.75 3.75 0 0 1 2.873 1.34l1.502 1.791-1.146 1.365L2.115 3.34A2.25 2.25 0 0 0 .39 3.5zM11.16 11.5h1.947l-1.017-1.018a.75.75 0 0 1 1.06-1.06L15.98 13l-2.83 3.578a.75.75 0 1 1-1.06-1.06l1.018-1.018H11.16a3.75 3.75 0 0 1-2.873-1.34l-1.502-1.791 1.146-1.365 1.504 1.791a2.25 2.25 0 0 0 1.725.804z"/></svg>
                    <span class="indicator-badge" id="shuf-badge">S</span>
                </button>
                <button class="c-btn" onclick="playPrev()"><svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M3.3 1a.7.7 0 0 1 .7.7v5.15l9.95-5.744a.7.7 0 0 1 1.05.606v12.575a.7.7 0 0 1-1.05.607L4 9.149V14.3a.7.7 0 0 1-1.4 0V1.7a.7.7 0 0 1 .7-.7z"/></svg></button>
                <button class="c-btn c-btn-play" id="btn-play" onclick="togglePlay()"><svg id="icon-play" style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M3 1.713a.7.7 0 0 1 1.05-.607l10.89 6.288a.7.7 0 0 1 0 1.212L4.05 14.894A.7.7 0 0 1 3 14.288V1.713z"/></svg></button>
                <button class="c-btn" onclick="playNext()"><svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M12.7 1a.7.7 0 0 0-.7.7v5.15L2.05 1.107A.7.7 0 0 0 1 1.712v12.575a.7.7 0 0 0 1.05.607L12 9.149V14.3a.7.7 0 0 0 1.4 0V1.7a.7.7 0 0 0-.7-.7z"/></svg></button>
                <button class="c-btn" id="btn-repeat" onclick="toggleRepeat()">
                    <svg style="width:16px;" viewBox="0 0 16 16"><path fill="currentColor" d="M0 4.75A3.75 3.75 0 0 1 3.75 1h8.5A3.75 3.75 0 0 1 16 4.75v5a3.75 3.75 0 0 1-3.75 3.75H9.81l1.018 1.018a.75.75 0 1 1-1.06 1.06L6.939 12.75l2.829-2.828a.75.75 0 1 1 1.06 1.06L9.811 12h2.439a2.25 2.25 0 0 0 2.25-2.25v-5a2.25 2.25 0 0 0-2.25-2.25h-8.5A2.25 2.25 0 0 0 1.5 4.75v5A2.25 2.25 0 0 0 3.75 12H5v1.5H3.75A3.75 3.75 0 0 1 0 9.75v-5z"/></svg>
                    <span class="indicator-badge" id="rep-badge">1</span>
                </button>
            </div>
            
            <div class="progress-wrap">
                <span id="time-current">0:00</span>
                <div class="prog-bg" id="seek-bg" onclick="seekAudio(event)">
                    <div class="prog-fill" id="seek-fill"></div>
                    <div class="prog-thumb" id="seek-thumb"></div>
                </div>
                <span id="time-total">0:00</span>
            </div>
        </div>
        
        <div class="p-right" style="justify-content:flex-end; gap:20px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <svg style="width:16px; color:var(--text-base);" viewBox="0 0 16 16"><path fill="currentColor" d="M9.741.85a.75.75 0 0 1 .375.65v13a.75.75 0 0 1-1.125.65l-6.925-4a3.642 3.642 0 0 1-1.33-4.967 3.639 3.639 0 0 1 1.33-1.332l6.925-4a.75.75 0 0 1 .75 0zm-6.924 5.3a2.139 2.139 0 0 0-1.049 1.85 2.14 2.14 0 0 0 1.049 1.85l5.958 3.44V2.71L2.817 6.15z"/></svg>
                <div class="vol-bg" id="vol-bg" onclick="setVolumeClick(event)">
                    <div class="prog-fill" id="vol-fill" style="width:100%;"></div>
                    <div class="prog-thumb" id="vol-thumb" style="left:100%;"></div>
                </div>
            </div>
        </div>
    </div>

    <audio id="mainAudio" crossorigin="anonymous"></audio>

    <script>
        // ==========================================
        // JS ENGINE V6: TEMPLATE LITERALS ONLY (NO SYNTAX ERRORS)
        // ==========================================
        
        let globalDatabase = []; 
        let playbackQueue = [];  
        let currentTrackIndex = -1;
        let isPlaying = false;
        
        let playlists = JSON.parse(localStorage.getItem('qlynktify_pl') || '{"Top Hits": [], "Liked Songs": []}');
        let localFolders = []; // Holds directory handles
        
        let shuffleMode = 0; 
        let repeatMode = 0;  
        let contextTrackObj = null; 
        let currentBlobUrl = null;  
        
        const audioEl = document.getElementById('mainAudio');
        const defaultCover = "https://qlynk.vercel.app/quicklink-logo.png";
        
        let audioCtx, analyser, dataArray, visualizerAnimId, parsedLyrics = [];

        // Restore Volume
        const savedVol = localStorage.getItem('qlynkVol');
        if(savedVol !== null) {
            audioEl.volume = parseFloat(savedVol);
            document.getElementById('vol-fill').style.width = `${audioEl.volume * 100}%`;
            document.getElementById('vol-thumb').style.left = `${audioEl.volume * 100}%`;
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg; t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2500);
        }

        // === CONTEXT MENU LOGIC ===
        document.addEventListener('contextmenu', e => {
            e.preventDefault(); closeAllMenus();
            const trackEl = e.target.closest('.track-row, .music-card');
            if(trackEl) openContextMenu(e, trackEl.getAttribute('data-id'), 'contextMenu');
            else openContextMenu(e, null, 'genericMenu');
        });
        document.addEventListener('click', e => { if(!e.target.closest('.context-menu')) closeAllMenus(); });

        function openContextMenu(e, trackId, menuId) {
            if(trackId) contextTrackObj = globalDatabase.find(t => t.track_id === trackId) || playbackQueue.find(t => t.track_id === trackId);
            const menu = document.getElementById(menuId);
            menu.style.display = 'block';
            let x = e.pageX, y = e.pageY;
            if(x + 220 > window.innerWidth) x = window.innerWidth - 230;
            if(y + 150 > window.innerHeight) y = window.innerHeight - 160;
            menu.style.left = `${x}px`; menu.style.top = `${y}px`;
            menu.classList.add('active');
        }
        function closeAllMenus() { document.querySelectorAll('.context-menu').forEach(m => { m.style.display='none'; m.classList.remove('active'); }); }

        function queueNext() {
            if(!contextTrackObj) return;
            if(currentTrackIndex === -1) { playSpecificTrack(contextTrackObj.track_id); return; }
            playbackQueue.splice(currentTrackIndex + 1, 0, contextTrackObj);
            showToast("Added to Play Next"); closeAllMenus();
        }
        function addToQueue() {
            if(!contextTrackObj) return;
            playbackQueue.push(contextTrackObj);
            showToast("Added to Queue"); closeAllMenus();
        }
        function saveToOfflineContext() { if(contextTrackObj) saveToOffline(contextTrackObj); closeAllMenus(); }
        
        function showAddToPlaylistMenu() {
            closeAllMenus();
            const m = document.getElementById('plSubMenu');
            m.innerHTML = Object.keys(playlists).map(k => `<div class="cm-item" onclick="addTrackToPl('${k}')">📋 ${k}</div>`).join('');
            m.style.display = 'block';
            m.classList.add('active');
            m.style.left = `${window.innerWidth/2}px`; m.style.top = `${window.innerHeight/2}px`;
        }
        function addTrackToPl(plName) {
            if(!contextTrackObj) return;
            if(!playlists[plName].find(t => t.track_id === contextTrackObj.track_id)) {
                playlists[plName].push(contextTrackObj);
                localStorage.setItem('qlynktify_pl', JSON.stringify(playlists));
                showToast(`Added to ${plName}`);
            } else { showToast("Already in playlist"); }
            closeAllMenus();
        }

        function createPlaylistAction() {
            const n = document.getElementById('plNameInput').value.trim();
            if(n && !playlists[n]) {
                playlists[n] = [];
                localStorage.setItem('qlynktify_pl', JSON.stringify(playlists));
                renderSidebarPlaylists();
                document.getElementById('plModal').style.display = 'none';
                document.getElementById('plNameInput').value = '';
                showToast("Playlist Created");
            }
        }

        // === INITIALIZATION ===
        async function initEngine() {
            try {
                const res = await fetch('/api/qlynktify/library');
                if (!res.ok) throw new Error("Auth Failed");
                const data = await res.json();
                globalDatabase = data.tracks.map(t => ({...t, source: 'cloud'}));
                
                // Sort Top Hits based on play_count (auto playlist)
                playlists["Top Hits"] = [...globalDatabase].sort((a,b) => (b.play_count || 0) - (a.play_count || 0)).slice(0, 50);
                
                playbackQueue = [...globalDatabase];
                
                renderSidebarPlaylists();
                renderHomeView();
                setupAudioEvents();
                setupKeyboardShortcuts();
                
                // IndexedDB offline track hydration
                const offline = await getOfflineTracks();
                offline.forEach(o => {
                    const m = globalDatabase.find(t => t.slug === o.slug);
                    if(m) m.offline = true;
                });
                
            } catch(e) { document.getElementById('auth-shield').style.display = 'flex'; }
        }

        // === VIEWS RENDERING (TEMPLATE LITERALS) ===
        function renderSidebarPlaylists() {
            const list = document.getElementById('sidebarPlaylists');
            list.innerHTML = Object.keys(playlists).map(k => `
                <div class="lib-item" onclick="renderPlaylistView('${k}')">
                    <div class="item-icon-box"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg> <span class="item-text">${k}</span></div>
                </div>
            `).join('');
        }
        
        function renderSidebarFolders() {
            const list = document.getElementById('sidebarLocalFolders');
            if(localFolders.length === 0) { list.innerHTML = `<div style="font-size:12px; color:var(--text-dim); padding:0 10px;">No folders added.</div>`; return; }
            list.innerHTML = localFolders.map((f, i) => `
                <div class="lib-item">
                    <div class="item-icon-box" onclick="renderFolderView(${i})"><svg viewBox="0 0 24 24"><path fill="currentColor" d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg> <span class="item-text">${f.name}</span></div>
                    <button class="btn-icon" style="padding:2px; color:#ff5555;" onclick="removeFolder(${i})">✖</button>
                </div>
            `).join('');
        }

        function renderHomeView() {
            const cont = document.getElementById('dynamicContent');
            const h = new Date().getHours();
            const gr = h < 12 ? 'Good morning' : (h < 18 ? 'Good afternoon' : 'Good evening');
            
            let html = `<h1 style="font-size:36px; font-weight:900; margin-bottom:30px; letter-spacing:-1px;">${gr}</h1>`;
            
            // Top Cards
            html += `<div class="section-title">Your Heavy Rotation</div><div class="card-grid">`;
            const mix = [...globalDatabase].sort(()=>0.5-Math.random()).slice(0, 6);
            mix.forEach(t => {
                const img = (t.meta && t.meta.artwork) ? t.meta.artwork : defaultCover;
                html += `
                    <div class="music-card" data-id="${t.track_id}" onclick="playSpecificTrack('${t.track_id}')">
                        <div class="mc-img-wrap"><img src="${img}" class="mc-img" id="card-img-${t.track_id}">
                        <div class="mc-play-btn"><svg style="width:24px;" viewBox="0 0 24 24"><path fill="currentColor" d="M8 5v14l11-7z"/></svg></div></div>
                        <div class="mc-title">${t.clean_title}</div><div class="mc-desc">${t.artist_guess || 'Vault'}</div>
                    </div>`;
            });
            html += `</div>`;

            html += `<div class="section-title">Vault Additions</div>`;
            html += generateTrackTable(globalDatabase.slice(0, 50));
            cont.innerHTML = html;
        }

        function renderQueueView() {
            const cont = document.getElementById('dynamicContent');
            let html = `<h1 style="font-size:36px; font-weight:900; margin-bottom:10px;">Play Queue</h1>`;
            if(playbackQueue.length === 0) { cont.innerHTML = html + `<div style="color:var(--text-base); margin-top:20px;">Queue empty.</div>`; return; }
            
            if(currentTrackIndex !== -1) {
                html += `<h3>Now Playing</h3>${generateTrackTable([playbackQueue[currentTrackIndex]], true)}`;
                html += `<h3 style="margin-top:30px; margin-bottom:10px;">Next Up</h3>`;
                const upNext = playbackQueue.slice(currentTrackIndex + 1);
                if(upNext.length > 0) html += generateTrackTable(upNext);
            } else { html += generateTrackTable(playbackQueue); }
            cont.innerHTML = html;
        }

        function renderPlaylistView(name) {
            const cont = document.getElementById('dynamicContent');
            const arr = playlists[name] || [];
            playbackQueue = [...arr]; // Set queue Context
            let html = `
                <div class="hero-banner">
                    <img src="${arr.length > 0 && arr[0].meta ? arr[0].meta.artwork : defaultCover}" class="hero-img">
                    <div class="hero-info">
                        <span class="hero-type">PLAYLIST</span>
                        <div class="hero-title">${name}</div>
                        <span class="hero-stats">${arr.length} tracks in this collection.</span>
                    </div>
                </div>
                <button class="btn-solid" style="width:auto; margin-bottom:30px;" onclick="if(playbackQueue.length>0) playSpecificTrack(playbackQueue[0].track_id)">PLAY ALL</button>
            `;
            html += generateTrackTable(arr);
            cont.innerHTML = html;
        }

        function generateTrackTable(arr, isNowPlayingBlock = false) {
            if(arr.length === 0) return `<div style="color:var(--text-dim);">No tracks found.</div>`;
            let html = `<table class="track-list"><thead><tr><th style="width:50px; text-align:center;">#</th><th>Title</th><th>Album</th><th style="text-align:right;">Plays</th></tr></thead><tbody>`;
            arr.forEach((t, i) => {
                const img = (t.meta && t.meta.artwork) ? t.meta.artwork : (t.artwork ? t.artwork : defaultCover);
                const active = (isNowPlayingBlock || (t.track_id === (playbackQueue[currentTrackIndex] || {}).track_id)) ? 'playing' : '';
                const bdg = t.source === 'local' ? `<span class="badge bg-local">Local</span>` : (t.offline ? `<span class="badge bg-offline">Offline</span>` : '');
                
                html += `
                    <tr class="track-row ${active}" data-id="${t.track_id}" onclick="playSpecificTrack('${t.track_id}')">
                        <td style="text-align:center; color:var(--text-dim);">${i+1}</td>
                        <td><div style="display:flex; align-items:center; gap:16px;">
                        <img src="${img}" class="t-img" id="tbl-img-${t.track_id}">
                        <div style="overflow:hidden;"><div class="t-title" title="${t.clean_title}">${t.clean_title} ${bdg}</div><div class="t-artist">${t.artist_guess || 'Vault'}</div></div></div></td>
                        <td style="color:var(--text-base); font-size:13px;">${t.meta ? t.meta.album : 'Qlynk'}</td>
                        <td style="text-align:right; color:var(--text-dim); font-size:13px;">${t.play_count || 0}</td>
                    </tr>`;
            });
            return html + `</tbody></table>`;
        }

        // === THE ULTIMATE ANTI-PIRACY BLOB ENGINE ===
        async function playSpecificTrack(trackId) {
            let idx = playbackQueue.findIndex(t => t.track_id === trackId);
            if(idx === -1) {
                playbackQueue = [...globalDatabase];
                if(shuffleMode > 0) applyShuffle();
                idx = playbackQueue.findIndex(t => t.track_id === trackId);
            }
            
            currentTrackIndex = idx;
            const track = playbackQueue[currentTrackIndex];
            
            // Re-render UI
            if(document.querySelector('.hero-title')) renderPlaylistView(document.querySelector('.hero-title').innerText);
            else if(document.querySelector('.section-title')) renderHomeView(); 
            else renderQueueView();

            // 🛡️ FIX: Auto-open Right Panel (Lyrics/Visualizer) on first play
            // Add this below the render Queue/Home view line
            
            // Auto-open Right Panel for Lyrics and Visualizer!
            const rp = document.getElementById('rightPanel');
            if(!rp.classList.contains('active') && window.innerWidth > 900) { toggleRightPanel(); }

            // Use the real title from iTunes if available, else fallback to clean title
            const displayTitle = track.meta && track.meta.real_title ? track.meta.real_title : track.clean_title;
            
            document.getElementById('bp-title').innerText = "Buffering Chunk...";
            document.getElementById('rp-title').innerText = displayTitle;
            document.getElementById('blob-loader').style.display = 'inline-block';
            
            if(track.meta) updatePlayerMeta(track.meta);
            else if(track.artwork) updatePlayerMeta({artist: track.artist_guess, artwork: track.artwork});
            else {
                document.getElementById('bp-artist').innerText = track.artist_guess || "Unknown";
                document.getElementById('bp-cover').src = defaultCover;
                document.getElementById('rp-cover').src = defaultCover;
                document.documentElement.style.setProperty('--dom-color', '#121212');
                document.documentElement.style.setProperty('--dom-color-dim', 'rgba(18,18,18,0.1)');
            }

            audioEl.pause(); audioEl.currentTime = 0;
            if(currentBlobUrl) { URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
            
            try {
                if(track.source === 'local') {
                    const file = await track.handle.getFile();
                    currentBlobUrl = URL.createObjectURL(file);
                    audioEl.src = currentBlobUrl;
                } else if (track.offline) {
                    const blob = await getOfflineBlob(track.slug);
                    if(!blob) throw new Error("Offline Corrupt");
                    currentBlobUrl = URL.createObjectURL(blob);
                    audioEl.src = currentBlobUrl;
                } else {
                    // Fetch 5-Min Token
                    const tokenRes = await fetch(`/api/qlynktify/generate_stream/${track.slug}`);
                    if(!tokenRes.ok) throw new Error("Auth Denied");
                    const tokenData = await tokenRes.json();
                    
                    // Assign endpoint to Audio tag. 
                    // Browser automatically sends Range requests. Backend caps at 512KB (30s).
                    // Browser fetches next chunk dynamically before ending! RAM saved.
                    audioEl.src = `/stream/audio/qlynktify/${tokenData.stream_token}`;
                }
                
                audioEl.play().then(() => {
                    document.getElementById('blob-loader').style.display = 'none';
                    document.getElementById('bp-title').innerText = track.clean_title;
                    isPlaying = true; updatePlayIcon();
                    
                    // Play Count Increment (Hit API once)
                    if(track.source === 'cloud') {
                        setTimeout(() => { fetch(`/api/qlynktify/increment_play/${track.slug}`, {method: 'POST'}); }, 10000);
                    }
                }).catch(e => { throw e; });
                
                fetchLyrics(track.search_query || track.clean_title);
                if(document.getElementById('rightPanel').classList.contains('active')) initVisualizer();
            } catch(e) {
                console.error("Playback Error:", e);
                document.getElementById('blob-loader').style.display = 'none';
                document.getElementById('bp-title').innerText = "Playback Failed";
                isPlaying = false; updatePlayIcon();
            }
        }

        function updatePlayerMeta(meta) {
            document.getElementById('bp-artist').innerText = meta.artist;
            document.getElementById('rp-artist').innerText = meta.artist;
            if(meta.artwork) {
                document.getElementById('bp-cover').src = meta.artwork;
                document.getElementById('rp-cover').src = meta.artwork;
                extractDominantColor(meta.artwork);
            }
        }

        // === CONTROLS ===
        function togglePlay() {
            if(currentTrackIndex === -1 && playbackQueue.length > 0) { playSpecificTrack(playbackQueue[0].track_id); return; }
            if(!audioEl.src) return;
            if(isPlaying) { audioEl.pause(); isPlaying = false; }
            else { audioEl.play(); isPlaying = true; }
            updatePlayIcon();
        }

        function playNext() {
            if(playbackQueue.length === 0) return;
            let nextIdx = currentTrackIndex + 1;
            if(nextIdx >= playbackQueue.length) {
                if(repeatMode === 1) nextIdx = 0; else return;
            }
            playSpecificTrack(playbackQueue[nextIdx].track_id);
        }

        function playPrev() {
            if(playbackQueue.length === 0) return;
            if(audioEl.currentTime > 4) audioEl.currentTime = 0;
            else {
                let prevIdx = currentTrackIndex - 1;
                if(prevIdx < 0) prevIdx = playbackQueue.length - 1;
                playSpecificTrack(playbackQueue[prevIdx].track_id);
            }
        }

        function updatePlayIcon() {
            const icon = document.getElementById('icon-play');
            if(isPlaying) icon.innerHTML = '<path fill="currentColor" d="M2.7 1a.7.7 0 0 0-.7.7v12.6a.7.7 0 0 0 .7.7h2.6a.7.7 0 0 0 .7-.7V1.7a.7.7 0 0 0-.7-.7H2.7zm8 0a.7.7 0 0 0-.7.7v12.6a.7.7 0 0 0 .7.7h2.6a.7.7 0 0 0 .7-.7V1.7a.7.7 0 0 0-.7-.7h-2.6z"/>';
            else icon.innerHTML = '<path fill="currentColor" d="M3 1.713a.7.7 0 0 1 1.05-.607l10.89 6.288a.7.7 0 0 1 0 1.212L4.05 14.894A.7.7 0 0 1 3 14.288V1.713z"/>';
        }

        function toggleShuffle() {
            shuffleMode = (shuffleMode + 1) % 3;
            const btn = document.getElementById('btn-shuffle');
            const badge = document.getElementById('shuf-badge');
            if(shuffleMode === 0) { btn.classList.remove('active'); badge.style.display = 'none'; }
            if(shuffleMode === 1) { btn.classList.add('active'); badge.style.display = 'block'; badge.innerText = 'N'; }
            if(shuffleMode === 2) { btn.classList.add('active'); badge.style.display = 'block'; badge.innerText = 'S'; }
            applyShuffle();
        }

        function applyShuffle() {
            if(playbackQueue.length <= 1) return;
            const currentTrack = currentTrackIndex > -1 ? playbackQueue[currentTrackIndex] : null;
            let pool = playbackQueue.filter(t => t !== currentTrack);
            if(shuffleMode === 0) playbackQueue = [...globalDatabase];
            else if(shuffleMode === 1) {
                for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
                playbackQueue = currentTrack ? [currentTrack, ...pool] : pool;
            }
            else if(shuffleMode === 2) {
                if(currentTrack && currentTrack.artist_guess) {
                    pool.sort((a,b) => (b.artist_guess === currentTrack.artist_guess ? 1 : 0) - (a.artist_guess === currentTrack.artist_guess ? 1 : 0));
                }
                playbackQueue = currentTrack ? [currentTrack, ...pool] : pool;
            }
            if(currentTrack) currentTrackIndex = 0; 
            if(document.querySelector('h1').innerText === 'Play Queue') renderQueueView();
        }

        function toggleRepeat() {
            repeatMode = (repeatMode + 1) % 3;
            const btn = document.getElementById('btn-repeat');
            const badge = document.getElementById('rep-badge');
            if(repeatMode === 0) { btn.classList.remove('active'); badge.style.display = 'none'; }
            if(repeatMode === 1) { btn.classList.add('active'); badge.style.display = 'block'; badge.innerText = 'Q'; }
            if(repeatMode === 2) { btn.classList.add('active'); badge.style.display = 'block'; badge.innerText = '1'; }
        }

        function setupAudioEvents() {
            audioEl.addEventListener('timeupdate', () => {
                if(!audioEl.duration) return;
                const p = (audioEl.currentTime / audioEl.duration) * 100;
                document.getElementById('seek-fill').style.width = `${p}%`; document.getElementById('seek-thumb').style.left = `${p}%`;
                document.getElementById('time-current').innerText = formatTime(audioEl.currentTime); document.getElementById('time-total').innerText = formatTime(audioEl.duration);
                syncLyrics();
            });
            audioEl.addEventListener('ended', () => { if(repeatMode === 2) { audioEl.currentTime = 0; audioEl.play(); } else playNext(); });
            
            // Native Buffering Events
            audioEl.addEventListener('waiting', () => document.getElementById('blob-loader').style.display = 'inline-block');
            audioEl.addEventListener('playing', () => document.getElementById('blob-loader').style.display = 'none');
        }
        
        function seekAudio(e) {
            if(!audioEl.duration) return;
            const bg = document.getElementById('seek-bg');
            audioEl.currentTime = (e.offsetX / bg.offsetWidth) * audioEl.duration;
        }

        function setVolumeClick(e) {
            const bg = document.getElementById('vol-bg');
            let p = Math.max(0, Math.min(1, e.offsetX / bg.offsetWidth));
            audioEl.volume = p; localStorage.setItem('qlynkVol', p);
            document.getElementById('vol-fill').style.width = `${p * 100}%`; document.getElementById('vol-thumb').style.left = `${p * 100}%`;
        }
        function formatTime(s) { if(!s || isNaN(s)) return "0:00"; let m = Math.floor(s/60); let sec = Math.floor(s%60); return `${m}:${sec<10?"0":""}${sec}`; }

        function setupKeyboardShortcuts() {
            document.addEventListener('keydown', e => {
                if(e.target.tagName === 'INPUT') return;
                let prevent = false;
                if(e.code === 'Space') { togglePlay(); prevent = true; showToast(isPlaying ? "Play" : "Pause"); }
                if(e.code === 'ArrowRight') { if(audioEl.duration) audioEl.currentTime += 5; prevent = true; }
                if(e.code === 'ArrowLeft') { if(audioEl.duration) audioEl.currentTime -= 5; prevent = true; }
                if(prevent) e.preventDefault();
            });
        }

       // === DUAL ENGINE: LYRICS ===
        async function fetchLyrics(query) {
            const container = document.getElementById('lyricsContainer');
            container.innerHTML = '<div style="text-align:center; color:rgba(255,255,255,0.3); margin-top:50px;">Scanning Datacenter...</div>';
            parsedLyrics = [];
            
            try {
                const res = await fetch(`/api/qlynktify/lyrics?q=${encodeURIComponent(query)}`);
                if(!res.ok) throw new Error("Lyrics API Error");
                const data = await res.json();
                
                if(data.synced) {
                    const lines = data.synced.split('\n');
                    lines.forEach(line => {
                        const match = line.match(/\[(\d{2}):(\d{2}\.\d{2})\](.*)/);
                        if(match) {
                            const time = parseInt(match[1]) * 60 + parseFloat(match[2]);
                            const text = match[3].trim();
                            if(text) parsedLyrics.push({time: time, text: text});
                        }
                    });
                    
                    if(parsedLyrics.length > 0) {
                        container.innerHTML = parsedLyrics.map((l, i) => `<div class="lyric-line" id="lyr-${i}" onclick="audioEl.currentTime=${l.time}">${l.text}</div>`).join('');
                        return;
                    }
                }
                
                // Fallback UI with Custom Search
                let fallbackHtml = `
                    <div style="background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; margin-top: 20px;">
                        <div style="font-size:14px; margin-bottom:15px; color:var(--text-base); font-weight:bold;">Synced lyrics not found. Refine your search query:</div>
                        <input type="text" id="manualLyricQuery" style="width:100%; padding:12px 16px; border-radius:24px; border:1px solid rgba(255,255,255,0.2); background:#121212; color:#fff; font-size:14px; margin-bottom:15px; outline:none;" value="${query}">
                        <button style="background:var(--text-bright); color:#000; font-weight:bold; padding:10px 24px; border-radius:24px; border:none; cursor:pointer;" onclick="fetchLyrics(document.getElementById('manualLyricQuery').value)">Search Datacenter</button>
                    </div>
                `;
                
                if(data.plain) {
                    fallbackHtml += `<div style="font-size:18px; white-space:pre-wrap; color:var(--text-base); text-align:center; line-height:1.6; margin-top:30px;">${data.plain}</div>`;
                }
                container.innerHTML = fallbackHtml;
                
            } catch(e) {
                container.innerHTML = `
                    <div style="background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; margin-top: 20px;">
                        <div style="font-size:14px; margin-bottom:15px; color:#ff5555; font-weight:bold;">Server error connecting to Lyrics Datacenter.</div>
                        <input type="text" id="manualLyricQuery" style="width:100%; padding:12px 16px; border-radius:24px; border:1px solid rgba(255,255,255,0.2); background:#121212; color:#fff; font-size:14px; margin-bottom:15px; outline:none;" value="${query}">
                        <button style="background:var(--text-bright); color:#000; font-weight:bold; padding:10px 24px; border-radius:24px; border:none; cursor:pointer;" onclick="fetchLyrics(document.getElementById('manualLyricQuery').value)">Retry Request</button>
                    </div>`;
            }
        }

        function syncLyrics() {
            if(parsedLyrics.length === 0) return;
            const curTime = audioEl.currentTime;
            for(let i=0; i<parsedLyrics.length; i++) {
                if(curTime >= parsedLyrics[i].time && (i === parsedLyrics.length - 1 || curTime < parsedLyrics[i+1].time)) {
                    const activeEl = document.getElementById(`lyr-${i}`);
                    if(activeEl && !activeEl.classList.contains('active')) {
                        document.querySelectorAll('.lyric-line').forEach(el => el.classList.remove('active'));
                        activeEl.classList.add('active');
                        const c = document.getElementById('lyricsContainer');
                        c.scrollTo({ top: activeEl.offsetTop - c.offsetTop - (c.clientHeight / 2) + 20, behavior: 'smooth' });
                    }
                    break;
                }
            }
        }

        // === VISUALIZER & COLOR ENGINE ===
        function initVisualizer() {
            if(visualizerAnimId) cancelAnimationFrame(visualizerAnimId);
            try {
                if(!audioCtx) {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    audioCtx = new AudioContext();
                    analyser = audioCtx.createAnalyser();
                    analyser.fftSize = 256; // High Detail
                    const source = audioCtx.createMediaElementSource(audioEl);
                    source.connect(analyser);
                    analyser.connect(audioCtx.destination);
                    dataArray = new Uint8Array(analyser.frequencyBinCount);
                }
                if(audioCtx.state === 'suspended') audioCtx.resume();
            } catch(e) { console.log("Visualizer Error:", e); return; }
            
            const canvas = document.getElementById('canvasVisualizer');
            const ctx = canvas.getContext('2d');
            
            function draw() {
                visualizerAnimId = requestAnimationFrame(draw);
                // 🛡️ Ensure canvas matches its container perfectly
                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = canvas.parentElement.clientHeight;
                
                analyser.getByteFrequencyData(dataArray);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const barWidth = (canvas.width / dataArray.length) * 2;
                const centerY = canvas.height / 2;
                let x = 0;
                
                for(let i = 0; i < dataArray.length; i++) {
                    const barHeight = (dataArray[i] / 255) * (canvas.height / 2) * 0.9;
                    // 🔥 COLOR MATCH: Using the dominant color variable
                    const domColor = getComputedStyle(document.documentElement).getPropertyValue('--dom-color').trim() || '#bc8cff';
                    
                    ctx.fillStyle = domColor;
                    // Draw Bars (Mirror effect)
                    ctx.fillRect(x, centerY - barHeight, barWidth - 1, barHeight); 
                    ctx.fillRect(x, centerY, barWidth - 1, barHeight); 
                    x += barWidth;
                }
            }
            draw();
        }

        function extractDominantColor(imgSrc) {
            const img = new Image(); img.crossOrigin = "Anonymous"; img.src = imgSrc;
            img.onload = () => {
                const c = document.createElement('canvas'); const ctx = c.getContext('2d');
                c.width = img.width; c.height = img.height; ctx.drawImage(img, 0, 0);
                try {
                    const data = ctx.getImageData(0,0,c.width,c.height).data; let r=0,g=0,b=0, count=0;
                    for(let i=0; i<data.length; i+=16) { r+=data[i]; g+=data[i+1]; b+=data[i+2]; count++; }
                    const R = ~~(r/count), G = ~~(g/count), B = ~~(b/count);
                    document.documentElement.style.setProperty('--dom-color', `rgb(${R},${G},${B})`);
                    document.documentElement.style.setProperty('--dom-color-dim', `rgba(${R},${G},${B}, 0.25)`);
                } catch(e) {}
            };
        }

        function toggleRightPanel() {
            const panel = document.getElementById('rightPanel'); panel.classList.toggle('active');
            if(panel.classList.contains('active')) { if(document.querySelector('.pt-btn:nth-child(2)').classList.contains('active')) initVisualizer(); } 
            else if(visualizerAnimId) cancelAnimationFrame(visualizerAnimId);
        }

        function switchRightPanel(mode) {
            const btnLyr = document.querySelector('.pt-btn:nth-child(1)'); const btnVis = document.querySelector('.pt-btn:nth-child(2)');
            const lyrC = document.getElementById('lyricsContainer'); const visC = document.getElementById('visualsContainer');
            if(mode === 'lyrics') {
                btnLyr.classList.add('active'); btnVis.classList.remove('active');
                lyrC.style.display = 'flex'; visC.style.display = 'none';
                if(visualizerAnimId) cancelAnimationFrame(visualizerAnimId);
            } else {
                btnVis.classList.add('active'); btnLyr.classList.remove('active');
                visC.style.display = 'flex'; lyrC.style.display = 'none';
                initVisualizer();
            }
        }

        // === LOCAL EDGE ENGINE WITH ID3 ARTWORK (jsmediatags) ===
        async function linkLocalFolder() {
            try {
                if(!('showDirectoryPicker' in window)) return alert("Use HTTPS.");
                const dirHandle = await window.showDirectoryPicker();
                localFolders.push(dirHandle); renderSidebarFolders();
                showToast("Scanning folder...");
                
                let added = 0;
                for await (const entry of dirHandle.values()) {
                    if(entry.kind === 'file' && entry.name.match(/\.(mp3|wav|m4a|ogg|flac)$/i)) {
                        const file = await entry.getFile();
                        let trackObj = {
                            track_id: `loc-${Math.random().toString(36).substr(2, 9)}`,
                            clean_title: entry.name.replace(/\.[^/.]+$/, "").replace(/_/g, " "),
                            artist_guess: "Local System",
                            source: 'local', handle: entry, play_count: 0
                        };

                        if(window.jsmediatags) {
                            jsmediatags.read(file, {
                                onSuccess: function(tag) {
                                    const tags = tag.tags;
                                    if(tags.title) trackObj.clean_title = tags.title;
                                    if(tags.artist) trackObj.artist_guess = tags.artist;
                                    if(tags.picture) {
                                        let b64 = ""; for (let i = 0; i < tags.picture.data.length; i++) b64 += String.fromCharCode(tags.picture.data[i]);
                                        trackObj.artwork = `data:${tags.picture.format};base64,${window.btoa(b64)}`;
                                    }
                                    globalDatabase.unshift(trackObj); playbackQueue.unshift(trackObj);
                                    if(document.querySelector('.section-title')) renderHomeView();
                                },
                                onError: function() { globalDatabase.unshift(trackObj); playbackQueue.unshift(trackObj); if(document.querySelector('.section-title')) renderHomeView(); }
                            });
                        } else { globalDatabase.unshift(trackObj); playbackQueue.unshift(trackObj); if(document.querySelector('.section-title')) renderHomeView(); }
                        added++;
                    }
                }
                showToast(`Added ${added} local tracks`);
            } catch(e) {}
        }
        
        function removeFolder(idx) {
            localFolders.splice(idx, 1);
            // Remove local tracks from memory (Simplified: removes all local for safety)
            globalDatabase = globalDatabase.filter(t => t.source !== 'local');
            playbackQueue = [...globalDatabase];
            renderSidebarFolders(); renderHomeView();
            showToast("Local edge disconnected");
        }

        // === OFFLINE DRM STORAGE ===
        const dbName = "QlynktifyOfflineDB";
        let dbPromise = new Promise((resolve, reject) => {
            const req = indexedDB.open(dbName, 1);
            req.onupgradeneeded = e => { e.target.result.createObjectStore("tracks", { keyPath: "slug" }); };
            req.onsuccess = e => resolve(e.target.result);
            req.onerror = () => reject();
        });

        async function saveToOffline(track) {
            if(track.source === 'local' || track.offline) { showToast("Already Offline/Local"); return; }
            showToast("Downloading to DRM Storage...");
            try {
                const tokenRes = await fetch(`/api/qlynktify/generate_stream/${track.slug}`);
                if(!tokenRes.ok) throw new Error("Auth");
                const tokenData = await tokenRes.json();
                
                const blobRes = await fetch(`/stream/audio/qlynktify/${tokenData.stream_token}`);
                if(!blobRes.ok) throw new Error("Download");
                const blob = await blobRes.blob();
                
                const db = await dbPromise;
                const tx = db.transaction("tracks", "readwrite");
                tx.objectStore("tracks").put({ slug: track.slug, blob: blob });
                
                track.offline = true;
                if(document.querySelector('.section-title')) renderHomeView(); else renderQueueView();
                showToast("✅ Saved Offline!");
            } catch(e) { showToast("Download Failed"); }
        }

        async function getOfflineTracks() {
            try {
                const db = await dbPromise;
                return new Promise(res => {
                    const req = db.transaction("tracks").objectStore("tracks").getAll();
                    req.onsuccess = () => res(req.result || []); req.onerror = () => res([]);
                });
            } catch(e) { return []; }
        }
        async function getOfflineBlob(slug) {
            try {
                const db = await dbPromise;
                return new Promise(res => {
                    const req = db.transaction("tracks").objectStore("tracks").get(slug);
                    req.onsuccess = () => res(req.result ? req.result.blob : null); req.onerror = () => res(null);
                });
            } catch(e) { return null; }
        }

        // Boot Engine
        initEngine();
    </script>
</body>
</html>
"""

@app.get("/qlynk-tify", response_class=HTMLResponse)
async def serve_qlynktify(request: Request):
    return HTMLResponse(content=QLYNKTIFY_HTML)

# ==========================================
# END OF QLYNK ARCHITECTURE V6 (TITAN)
# ==========================================

# ==========================================
# END OF QLYNK ARCHITECTURE V5 (BLOB ENGINE)
# ==========================================

# ==========================================
# END OF FILE
# --- SYSTEM HIBERNATION INITIATED ---
# Developer Status: Offline. 
# Mission: IIT Kharagpur CSE. 
# Last Update: 19:20-28pm || 13 April 2026 IST || 20:02 pm
# ==========================================
# ==========================================
# END OF QLYNK ARCHITECTURE V2
# ==========================================

# ==========================================
# END OF FILE
# --- SYSTEM HIBERNATION INITIATED ---
# Developer Status: Offline. 
# Mission: IIT Kharagpur CSE. 
# Last Update: 13:59pm || 13 April 2026 IST
# GO STUDY! ANNUAL EXAMS AND JEE ARE COMING. NO MORE COMMITS. 🚀📚
# ==========================================

# ==========================================
# END OF FILE (FOR REAL THIS TIME! GO STUDY!)
# ==========================================
