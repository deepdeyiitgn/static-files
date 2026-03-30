import os
import json
import shutil
import uuid
import mimetypes
import logging
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

# Hugging Face API Client Initialization
api = HfApi(token=HF_TOKEN)
DATASET_REPO = os.environ.get("DATASET_REPO")

# ==========================================
# 2. ADVANCED FAST BOOT (LIFESPAN MANAGER)
# ==========================================
# Yeh function server start hone ke BAAD background mein chalta hai.
# Isse port 7860 block nahi hota aur Space immediately "Running" state mein aa jata hai.
@asynccontextmanager
async def lifespan(app: FastAPI):
    global DATASET_REPO
    logger.info("Starting Qlynk Host Initialization Sequence...")
    
    try:
        # Agar repo name user ne env mein nahi diya, toh automatic detect karo
        if not DATASET_REPO:
            user_info = api.whoami()
            username = user_info.get("name")
            DATASET_REPO = f"{username}/my-private-storage"
            logger.info(f"Auto-detected Target Repo: {DATASET_REPO}")
        
        # Private dataset create karna (agar exist nahi karta)
        api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", private=True, exist_ok=True)
        logger.info("Dataset Repository Verified & Ready.")
        
        # History JSON database setup karna
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

# Initialize FastAPI App with standard meta tags
app = FastAPI(
    title="Qlynk Host Ultimate",
    description="Enterprise-grade private file hosting architecture using HF Datasets.",
    version="2.0.0",
    lifespan=lifespan
)

# ==========================================
# 3. DYNAMIC CORS (DOMAIN WHITELISTING)
# ==========================================
# ENV variables (DOMAIN_1, DOMAIN_2...) ko check karke allowed domains banayega
allowed_origins = [val for key, val in os.environ.items() if key.startswith("DOMAIN_")]
if not allowed_origins:
    allowed_origins = ["*"] # Public fallback
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
    """Bytes ko KB, MB, GB mein format karne ke liye"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def get_db() -> Dict[str, Any]:
    """Hugging Face se latest database json download karta hai"""
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Database Read Error: {e}")
        return {"total_files": 0, "total_size_bytes": 0, "files": []}

def save_db(db_data: Dict[str, Any]):
    """Database ko update karke wapas Hugging Face par upload karta hai"""
    # Recalculate stats for safety
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

# Auth Middleware: Cookie ya Header dono se verify karta hai
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
    Yeh endpoint browser hit karne par pure system ka detailed documentation dega.
    Tum ise apni dusri websites par as a backend reference use kar sakte ho.
    """
    return {
        "system_info": {
            "name": "Qlynk Enterprise Storage Node",
            "version": "2.0.0",
            "status": "Online & Operational",
            "storage_provider": "Hugging Face Datasets"
        },
        "authentication_guide": {
            "method": "API Key / Password",
            "how_to_use": "Include your SPACE_PASSWORD in the request Headers as 'password: YOUR_PWD'."
        },
        "endpoints_documentation": {
            "1_UPLOAD_FILE": {
                "route": "POST /api/rest",
                "description": "Upload a new file to the storage node.",
                "required_headers": {"password": "Your secret password"},
                "form_data_parameters": {
                    "file": "[REQUIRED] The actual file binary.",
                    "slug": "[OPTIONAL] Custom URL friendly identifier. Auto-generated if blank.",
                    "title": "[OPTIONAL] Human readable title for the file.",
                    "thumbnail": "[OPTIONAL] URL pointing to an image thumbnail.",
                    "format": "[OPTIONAL] 'json' (returns metadata) OR 'redirect' (performs 308 redirect instantly)."
                },
                "success_response": "200 OK (JSON with file details and public URL)"
            },
            "2_UPDATE_METADATA": {
                "route": "PUT /api/rest/{current_slug}",
                "description": "Edit the title, thumbnail, or even the slug of an existing file.",
                "required_headers": {"password": "Your secret password"},
                "form_data_parameters": {
                    "new_slug": "[OPTIONAL] Change the public URL string.",
                    "title": "[OPTIONAL] Update the title.",
                    "thumbnail": "[OPTIONAL] Update the thumbnail URL."
                }
            },
            "3_DELETE_FILE": {
                "route": "DELETE /api/rest/{slug}",
                "description": "Permanently erase a file from the Hugging Face dataset.",
                "required_headers": {"password": "Your secret password"}
            },
            "4_FETCH_HISTORY": {
                "route": "GET /api/history",
                "description": "Get an array of all uploaded files. Supports search.",
                "query_params": {
                    "search": "[OPTIONAL] Filter files by title or filename."
                }
            },
            "5_SYSTEM_STATS": {
                "route": "GET /api/stats",
                "description": "Get server storage usage statistics."
            }
        },
        "error_reference": {
            "401": "Unauthorized - Password missing or wrong.",
            "404": "Not Found - The file or slug does not exist.",
            "409": "Conflict - The slug you are trying to use is already taken.",
            "500": "Internal Server Error - Usually an issue communicating with Hugging Face."
        }
    }

import requests # <--- Ye top par imports mein check kar lena

@app.post("/api/rest")
async def process_advanced_upload(
    file: UploadFile = File(None), # Ab file optional hai
    link_url: str = Form(None),    # Naya field link ke liye
    slug: str = Form(None),
    title: str = Form(None),
    thumbnail: str = Form(""),
    format: str = Form("json"),
    token: str = Depends(verify_auth)
):
    """File upload logic with deep metadata extraction & Backend Proxy"""
    db = get_db()
    files_list = db.get("files", [])
    
    final_slug = slug.strip() if slug and slug.strip() != "" else str(uuid.uuid4())[:8]
    if any(item["slug"] == final_slug for item in files_list):
        raise HTTPException(status_code=409, detail=f"ERROR: The slug '{final_slug}' is already assigned.")

    repo_path = ""
    filename = ""
    file_size = 0
    mime_type = "application/octet-stream"
    is_external = False
    external_url = ""

    # ==========================================
    # LOGIC 1: UPLOAD FROM URL (BACKEND PROXY)
    # ==========================================
    if link_url:
        filename = link_url.split('/')[-1].split('?')[0]
        if not filename or '.' not in filename:
            filename = "downloaded_file.bin"
        
        temp_path = f"/tmp/{final_slug}_{filename}"
        
        try:
            # Backend downloading the file directly
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            r = requests.get(link_url, stream=True, headers=headers, timeout=15)
            r.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(temp_path)
            mime_type, _ = mimetypes.guess_type(temp_path)
            if not mime_type:
                mime_type = r.headers.get('Content-Type', 'application/octet-stream')
            
            repo_path = f"files/{final_slug}_{filename}"
            logger.info(f"Uploading fetched file {filename} to {DATASET_REPO}...")
            api.upload_file(path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset")
            os.remove(temp_path)
            
        except Exception as e:
            # Failsafe: Create a 308 Redirect Entry if download fails
            logger.warning(f"Backend fetch failed: {e}. Creating 308 redirect entry instead.")
            is_external = True
            external_url = link_url
            filename = "External_Link"

    # ==========================================
    # LOGIC 2: STANDARD LOCAL FILE UPLOAD
    # ==========================================
    elif file:
        filename = file.filename
        temp_path = f"/tmp/{final_slug}_{filename}"
        repo_path = f"files/{final_slug}_{filename}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(temp_path)
        mime_type, _ = mimetypes.guess_type(temp_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        api.upload_file(path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset")
        os.remove(temp_path)
        
    else:
        raise HTTPException(status_code=400, detail="Must provide either a 'file' or 'link_url'.")

    # ==========================================
    # SAVE METADATA
    # ==========================================
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    
    file_record = {
        "slug": final_slug,
        "filename": filename,
        "path": repo_path,
        "title": title if title else filename,
        "thumbnail": thumbnail,
        "mime_type": mime_type,
        "size_bytes": file_size,
        "uploaded_at": upload_timestamp,
        "is_external": is_external,    # Tracking if it's a proxy 308 link
        "external_url": external_url   # Storing original URL
    }
    
    files_list.append(file_record)
    db["files"] = files_list
    save_db(db)
    
    if format.lower() == "redirect":
        return RedirectResponse(url=f"/f/{final_slug}", status_code=308)
    
    return {"status": "success", "message": "Asset Indexed", "metadata": file_record}
    

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
            # Check slug conflict if changing slug
            if new_slug and new_slug != current_slug:
                if any(x["slug"] == new_slug for x in files_list):
                    raise HTTPException(status_code=409, detail="New slug already exists in database.")
                item["slug"] = new_slug
            
            # Syntax fixed: 'is not None' use kiya gaya hai '!== None' ki jagah
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
            # HF se delete karo
            api.delete_file(path_in_repo=file_record["path"], repo_id=DATASET_REPO, repo_type="dataset")
        except Exception as e:
            logger.warning(f"File might already be deleted from HF: {e}")
            
        # DB se remove karo
        db["files"] = [item for item in files_list if item["slug"] != slug]
        save_db(db)
        return {"status": "success", "message": f"File '{slug}' deleted permanently."}
        
    raise HTTPException(status_code=404, detail="File not found in database.")

@app.get("/api/history")
async def fetch_advanced_history(search: Optional[str] = None, token: str = Depends(verify_auth)):
    db = get_db()
    files_list = db.get("files", [])
    
    # Search filtering
    if search:
        search_query = search.lower()
        files_list = [f for f in files_list if search_query in f.get("title", "").lower() or search_query in f.get("filename", "").lower()]
        
    # Return formatted sizes along with raw bytes
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
    """Yeh public route hai. External redirect fail-safe included."""
    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="404: The requested resource could not be found.")
        
    # 🛠️ NAYA: FAILSAFE 308 REDIRECT
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

    
# --- Static JS Assets ---
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

# --- UI Route ---
@app.get("/", response_class=HTMLResponse)
async def serve_frontend_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
        
    return HTMLResponse(content=html_content)