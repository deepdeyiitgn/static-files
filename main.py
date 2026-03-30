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

@app.post("/api/rest")
async def process_advanced_upload(
    file: UploadFile = File(...),
    slug: str = Form(None),
    title: str = Form(None),
    thumbnail: str = Form(""),
    format: str = Form("json"),
    token: str = Depends(verify_auth)
):
    """File upload logic with deep metadata extraction"""
    db = get_db()
    files_list = db.get("files", [])
    
    # URL Slug checking
    final_slug = slug.strip() if slug and slug.strip() != "" else str(uuid.uuid4())[:8]
    if any(item["slug"] == final_slug for item in files_list):
        raise HTTPException(status_code=409, detail=f"ERROR: The slug '{final_slug}' is already assigned to another file.")

    filename = file.filename
    repo_path = f"files/{final_slug}_{filename}"
    temp_path = f"/tmp/{final_slug}_{filename}"
    
    # 1. Save locally temporarily
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Extract Metadata
    file_size = os.path.getsize(temp_path)
    mime_type, _ = mimetypes.guess_type(temp_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    upload_timestamp = datetime.utcnow().isoformat() + "Z"
    
    # 3. Upload to HF
    logger.info(f"Uploading {filename} ({format_size(file_size)}) to {DATASET_REPO}...")
    api.upload_file(
        path_or_fileobj=temp_path, 
        path_in_repo=repo_path, 
        repo_id=DATASET_REPO, 
        repo_type="dataset"
    )
    os.remove(temp_path) # Clean up memory
    
    # 4. Save Database Record
    file_record = {
        "slug": final_slug,
        "filename": filename,
        "path": repo_path,
        "title": title if title else filename,
        "thumbnail": thumbnail,
        "mime_type": mime_type,
        "size_bytes": file_size,
        "uploaded_at": upload_timestamp
    }
    
    files_list.append(file_record)
    db["files"] = files_list
    save_db(db)
    logger.info(f"Upload successful. Slug: {final_slug}")
    
    # 5. Handle Redirection logic
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
    """Yeh public route hai. No password required. Browsers aur APIs idhar se data read karte hain."""
    db = get_db()
    file_record = next((item for item in db.get("files", []) if item["slug"] == slug), None)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="404: The requested resource could not be found.")
        
    try:
        # File HF Datasets se runtime par cache hoti hai
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
            content_disposition_type="inline" # 🛠️ YEH LINE FILE KO BROWSER MEIN OPEN KAREGI
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

# --- UI Route ---
@app.get("/", response_class=HTMLResponse)
async def serve_frontend_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()
        
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_frontend_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Qlynk Storage Node - Enterprise Dashboard</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {
                --bg-main: #050505; --bg-card: #121212; --bg-hover: #1e1e1e;
                --border-color: #333; --text-main: #ededed; --text-muted: #888;
                --brand-accent: #0070f3; --brand-danger: #e23636; --brand-success: #17c964;
                --radius-lg: 12px; --radius-sm: 6px;
                --font-stack: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            * { box-sizing: border-box; }
            body { margin: 0; padding: 0; background: var(--bg-main); color: var(--text-main); font-family: var(--font-stack); min-height: 100vh; }
            
            /* Navbar */
            .navbar { display: flex; justify-content: space-between; align-items: center; padding: 1rem 2rem; background: rgba(18, 18, 18, 0.8); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border-color); position: sticky; top: 0; z-index: 100;}
            .nav-brand { font-size: 1.2rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }
            .nav-brand i { color: var(--brand-accent); }
            
            /* Containers & Layout */
            .main-container { max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }
            .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 8px 30px rgba(0,0,0,0.12); transition: transform 0.2s; }
            
            /* Typography & Inputs */
            h1, h2, h3 { margin-top: 0; letter-spacing: -0.03em; }
            .text-muted { color: var(--text-muted); font-size: 0.9rem; }
            input.form-control, input[type="file"] { width: 100%; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); padding: 0.8rem 1rem; border-radius: var(--radius-sm); margin-bottom: 1rem; outline: none; transition: 0.2s; font-family: var(--font-stack); }
            input.form-control:focus { border-color: var(--brand-accent); box-shadow: 0 0 0 2px rgba(0, 112, 243, 0.2); }
            
            /* Buttons */
            .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 0.8rem 1.5rem; border: none; border-radius: var(--radius-sm); font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: var(--font-stack); }
            .btn-primary { background: var(--text-main); color: var(--bg-main); }
            .btn-primary:hover { background: #d4d4d4; transform: translateY(-1px); }
            .btn-outline { background: transparent; color: var(--text-main); border: 1px solid var(--border-color); }
            .btn-outline:hover { background: var(--bg-hover); }
            .btn-danger { background: rgba(226, 54, 54, 0.1); color: var(--brand-danger); border: 1px solid rgba(226, 54, 54, 0.3); }
            .btn-danger:hover { background: var(--brand-danger); color: white; }
            
            /* Stats Row */
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
            .stat-box { background: var(--bg-card); padding: 1.5rem; border-radius: var(--radius-lg); border: 1px solid var(--border-color); text-align: center; }
            .stat-box h3 { font-size: 2rem; margin: 0 0 0.5rem 0; color: var(--brand-accent); }
            
            /* File Grid Architecture */
            .search-bar-container { display: flex; gap: 10px; margin-bottom: 1rem; }
            .file-list { display: flex; flex-direction: column; gap: 1rem; }
            .file-item { display: flex; flex-direction: column; background: var(--bg-main); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; }
            .file-item-main { display: flex; align-items: center; padding: 1rem; gap: 1rem; }
            .file-thumb { width: 60px; height: 60px; border-radius: 8px; background: var(--bg-card); display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid var(--border-color); }
            .file-thumb img { width: 100%; height: 100%; object-fit: cover; }
            .file-thumb i { font-size: 1.5rem; color: var(--text-muted); }
            .file-details { flex-grow: 1; min-width: 0; }
            .file-title { font-weight: 600; font-size: 1.1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
            .file-meta { display: flex; gap: 15px; font-size: 0.85rem; color: var(--text-muted); flex-wrap: wrap; }
            .file-meta span { display: flex; align-items: center; gap: 4px; }
            .file-actions { display: flex; gap: 8px; padding-left: 1rem; border-left: 1px solid var(--border-color); }
            .icon-btn { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-main); cursor: pointer; transition: 0.2s; }
            .icon-btn:hover { background: var(--bg-hover); color: var(--brand-accent); }
            .icon-btn.delete:hover { color: var(--brand-danger); border-color: var(--brand-danger); }
            
            /* Toast Notification */
            #toast { visibility: hidden; min-width: 250px; background-color: var(--brand-success); color: #fff; text-align: center; border-radius: 6px; padding: 12px; position: fixed; z-index: 1000; left: 50%; bottom: 30px; transform: translateX(-50%); font-weight: 600; font-size: 0.9rem; box-shadow: 0 4px 12px rgba(0,0,0,0.3); opacity: 0; transition: opacity 0.3s, bottom 0.3s; }
            #toast.show { visibility: visible; opacity: 1; bottom: 50px; }
            #toast.error { background-color: var(--brand-danger); }

            /* Sections */
            #loginSection, #dashboardSection { display: none; }
            
            /* Responsive */
            @media (max-width: 600px) {
                .file-item-main { flex-direction: column; align-items: flex-start; }
                .file-actions { border-left: none; padding-left: 0; width: 100%; justify-content: flex-end; padding-top: 10px; border-top: 1px solid var(--border-color); margin-top: 10px;}
            }
        </style>
    </head>
    <body>

        <nav class="navbar">
            <div class="nav-brand"><i class="fa-solid fa-server"></i> Qlynk Enterprise Node</div>
            <button class="btn btn-outline" style="padding: 0.5rem 1rem; font-size: 0.85rem;" onclick="logout()" id="logoutBtn" style="display:none;"><i class="fa-solid fa-right-from-bracket"></i> Disconnect</button>
        </nav>

        <div class="main-container">
            
            <div id="loginSection" class="card" style="max-width: 450px; margin: 4rem auto; text-align: center; padding: 3rem 2rem;">
                <i class="fa-solid fa-lock" style="font-size: 3rem; color: var(--brand-accent); margin-bottom: 1.5rem;"></i>
                <h2>System Locked</h2>
                <p class="text-muted" style="margin-bottom: 2rem;">Authenticate with your Master Password to access the storage node.</p>
                <input type="password" id="pwd" class="form-control" placeholder="Enter Space Password..." onkeypress="if(event.key === 'Enter') login()">
                <button class="btn btn-primary" style="width: 100%;" onclick="login()">Unlock Infrastructure</button>
            </div>

            <div id="dashboardSection">
                
                <div class="stats-grid" id="statsContainer">
                    <div class="stat-box">
                        <h3 id="statFiles">0</h3>
                        <div class="text-muted">Total Files Hosted</div>
                    </div>
                    <div class="stat-box">
                        <h3 id="statSize">0 MB</h3>
                        <div class="text-muted">Storage Consumed</div>
                    </div>
                    <div class="stat-box">
                        <h3><i class="fa-solid fa-bolt" style="color: #f5a623;"></i></h3>
                        <div class="text-muted">HF Auto-Scaling Active</div>
                    </div>
                </div>

                <div class="card">
                    <h2><i class="fa-solid fa-cloud-arrow-up" style="margin-right: 8px;"></i> Upload Engine</h2>
                    <p class="text-muted">Push files directly to the HF Dataset using the internal REST API.</p>
                    <div style="background: var(--bg-main); padding: 1.5rem; border-radius: var(--radius-sm); border: 1px dashed var(--border-color); margin: 1.5rem 0;">
                        <input type="file" id="fileInput" class="form-control" style="border:none; padding: 0; background: transparent;">
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <input type="text" id="upTitle" class="form-control" placeholder="Friendly Title (e.g., Logo Vector)">
                        <input type="text" id="upSlug" class="form-control" placeholder="Custom Slug (e.g., company-logo)">
                    </div>
                    <input type="text" id="upThumb" class="form-control" placeholder="Thumbnail Image URL (Optional)">
                    
                    <button id="uploadBtn" class="btn btn-primary" onclick="uploadFile()">
                        <i class="fa-solid fa-paper-plane"></i> Execute Upload via API
                    </button>
                </div>

                <div class="card">
                    <h2><i class="fa-solid fa-database" style="margin-right: 8px;"></i> Dataset Explorer</h2>
                    
                    <div class="search-bar-container">
                        <input type="text" id="searchInput" class="form-control" placeholder="Search files by title or slug..." style="margin: 0;" onkeyup="searchFiles()">
                        <button class="btn btn-outline" onclick="loadDashboardData()"><i class="fa-solid fa-rotate-right"></i></button>
                    </div>
                    
                    <div class="file-list" id="fileList">
                        <div style="text-align:center; padding: 2rem; color: var(--text-muted);">Fetching dataset...</div>
                    </div>
                </div>
            </div>

        </div>

        <div id="toast">Notification Message</div>

        <script>
            // Utility: Show Toast
            function showToast(message, isError = false) {
                const toast = document.getElementById("toast");
                toast.innerText = message;
                toast.className = isError ? "show error" : "show";
                setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 3000);
            }

            // Authentication Logic
            window.onload = async () => {
                const cookies = document.cookie.split(';').find(c => c.trim().startsWith('auth_token='));
                if (cookies) {
                    const res = await fetch('/api/verify');
                    if (res.ok) { initApp(); return; }
                }
                document.getElementById('loginSection').style.display = 'block';
            };

            async function login() {
                const pwd = document.getElementById('pwd').value;
                const res = await fetch('/api/verify', { headers: { 'password': pwd } });
                if (res.ok) {
                    document.cookie = `auth_token=${pwd}; max-age=31536000; path=/; SameSite=Strict`;
                    initApp();
                } else {
                    showToast("Authentication Failed! Incorrect Password.", true);
                }
            }

            function logout() {
                document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                window.location.reload();
            }

            function initApp() {
                document.getElementById('loginSection').style.display = 'none';
                document.getElementById('dashboardSection').style.display = 'block';
                document.getElementById('logoutBtn').style.display = 'inline-flex';
                loadDashboardData();
            }

            // Data Fetching
            async function loadDashboardData() {
                fetchStats();
                fetchFiles();
            }

            async function fetchStats() {
                const res = await fetch('/api/stats');
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('statFiles').innerText = data.total_files;
                    document.getElementById('statSize').innerText = data.formatted_total_size;
                }
            }

            async function fetchFiles(query = "") {
                const url = query ? `/api/history?search=${encodeURIComponent(query)}` : '/api/history';
                const res = await fetch(url);
                if (res.ok) {
                    const data = await res.json();
                    renderFiles(data);
                }
            }

            let searchTimeout;
            function searchFiles() {
                clearTimeout(searchTimeout);
                const q = document.getElementById('searchInput').value;
                searchTimeout = setTimeout(() => fetchFiles(q), 300);
            }

            // Render UI
            function renderFiles(files) {
                const list = document.getElementById('fileList');
                if (files.length === 0) {
                    list.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted); border: 1px dashed var(--border-color); border-radius: 8px;">No files found in the dataset.</div>`;
                    return;
                }
                
                let html = "";
                files.forEach(item => {
                    const url = `${window.location.origin}/f/${item.slug}`;
                    const dateObj = new Date(item.uploaded_at);
                    const dateStr = isNaN(dateObj) ? "Unknown Date" : dateObj.toLocaleDateString();
                    
                    let thumbHtml = item.thumbnail 
                        ? `<img src="${item.thumbnail}" alt="thumb">`
                        : `<i class="fa-regular fa-file-lines"></i>`;

                    html += `
                        <div class="file-item">
                            <div class="file-item-main">
                                <div class="file-thumb">${thumbHtml}</div>
                                <div class="file-details">
                                    <div class="file-title">${item.title}</div>
                                    <div class="file-meta">
                                        <span><i class="fa-solid fa-link"></i> /f/${item.slug}</span>
                                        <span><i class="fa-solid fa-hard-drive"></i> ${item.formatted_size || 'Unknown'}</span>
                                        <span><i class="fa-regular fa-calendar"></i> ${dateStr}</span>
                                    </div>
                                </div>
                                <div class="file-actions">
                                    <button class="icon-btn" onclick="copyToClipboard('${url}')" title="Copy Public Link"><i class="fa-regular fa-copy"></i></button>
                                    <button class="icon-btn" onclick="editFile('${item.slug}', '${item.title.replace(/'/g, "\\'")}', '${item.thumbnail || ''}')" title="Edit Metadata"><i class="fa-solid fa-pen"></i></button>
                                    <button class="icon-btn delete" onclick="deleteFile('${item.slug}')" title="Delete File"><i class="fa-solid fa-trash-can"></i></button>
                                </div>
                            </div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }

            // Actions
            async function copyToClipboard(text) {
                try {
                    await navigator.clipboard.writeText(text);
                    showToast("Public link copied to clipboard!");
                } catch (err) {
                    showToast("Failed to copy link.", true);
                }
            }

            async function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                const file = fileInput.files[0];
                if (!file) { showToast("Please select a file first.", true); return; }

                const btn = document.getElementById('uploadBtn');
                btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Uploading to HF...';
                btn.disabled = true;

                const formData = new FormData();
                formData.append('file', file);
                
                const slug = document.getElementById('upSlug').value;
                const title = document.getElementById('upTitle').value;
                const thumb = document.getElementById('upThumb').value;
                
                if(slug) formData.append('slug', slug);
                if(title) formData.append('title', title);
                if(thumb) formData.append('thumbnail', thumb);

                try {
                    const res = await fetch('/api/rest', { method: 'POST', body: formData });
                    const data = await res.json();
                    
                    if (res.ok) {
                        showToast("File successfully hosted!");
                        fileInput.value = "";
                        document.getElementById('upSlug').value = "";
                        document.getElementById('upTitle').value = "";
                        document.getElementById('upThumb').value = "";
                        loadDashboardData();
                    } else {
                        showToast(data.detail || "Upload failed due to a conflict.", true);
                    }
                } catch (e) {
                    showToast("Network error during upload.", true);
                } finally {
                    btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Execute Upload via API';
                    btn.disabled = false;
                }
            }

            async function editFile(oldSlug, oldTitle, oldThumb) {
                const newTitle = prompt("Update Title:", oldTitle);
                if (newTitle === null) return;
                
                const newThumb = prompt("Update Thumbnail URL (Leave empty to remove):", oldThumb);
                if (newThumb === null) return;

                const formData = new FormData();
                formData.append('title', newTitle);
                formData.append('thumbnail', newThumb);

                const res = await fetch(`/api/rest/${oldSlug}`, { method: 'PUT', body: formData });
                if (res.ok) {
                    showToast("Metadata updated successfully!");
                    fetchFiles(document.getElementById('searchInput').value);
                } else {
                    showToast("Failed to update metadata.", true);
                }
            }

            async function deleteFile(slug) {
                if (!confirm(`WARNING: Are you sure you want to permanently delete '${slug}'? This cannot be undone.`)) return;
                
                const res = await fetch(`/api/rest/${slug}`, { method: 'DELETE' });
                if (res.ok) {
                    showToast("File permanently deleted.");
                    loadDashboardData();
                } else {
                    showToast("Error deleting file.", true);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)