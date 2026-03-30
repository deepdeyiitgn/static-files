import os
import json
import shutil
from fastapi import FastAPI, HTTPException, Header, Cookie, UploadFile, File, Form, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError
import uuid

app = FastAPI()

# Secrets
HF_TOKEN = os.environ.get("HF_TOKEN")
SPACE_PASSWORD = os.environ.get("SPACE_PASSWORD")

# Dynamic Domain Whitelisting (CORS)
allowed_origins = []
for key, value in os.environ.items():
    if key.startswith("DOMAIN_"):
        allowed_origins.append(value)

if not allowed_origins:
    allowed_origins = ["*"] # Fallback if no domains provided

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = HfApi(token=HF_TOKEN)

# Auto-detect Username & Setup Repo
try:
    user_info = api.whoami()
    USERNAME = user_info["name"]
    DATASET_REPO = os.environ.get("DATASET_REPO", f"{USERNAME}/my-private-storage")
except Exception as e:
    DATASET_REPO = None
    print(f"HF Authentication failed: {e}")

def init_repo():
    if not HF_TOKEN or not DATASET_REPO:
        return
    try:
        api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", private=True, exist_ok=True)
        try:
            hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
        except EntryNotFoundError:
            with open("history.json", "w") as f:
                json.dump([], f)
            api.upload_file(path_or_fileobj="history.json", path_in_repo="history.json", repo_id=DATASET_REPO, repo_type="dataset")
    except Exception as e:
        print(f"Repo Init Error: {e}")

init_repo()

# Helper Functions
def get_history():
    try:
        file_path = hf_hub_download(repo_id=DATASET_REPO, filename="history.json", repo_type="dataset", token=HF_TOKEN)
        with open(file_path, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history_data):
    with open("history.json", "w") as f:
        json.dump(history_data, f)
    api.upload_file(path_or_fileobj="history.json", path_in_repo="history.json", repo_id=DATASET_REPO, repo_type="dataset")

# Authentication Dependency (Checks Header OR Cookie)
def verify_auth(password: str = Header(None), auth_token: str = Cookie(None)):
    token = password or auth_token
    if token != SPACE_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Password")
    return token

# --- UI Route ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.post("/api/verify")
async def verify_login(token: str = Depends(verify_auth)):
    return {"status": "ok"}

# --- The Mega REST API ---

@app.get("/api/rest", response_class=JSONResponse)
async def rest_api_docs():
    """Shows REST API documentation on direct browser hit"""
    return {
        "app": "Qlynk Private File Host API",
        "description": "A fully customized API to host files directly to Hugging Face datasets.",
        "authentication": "Pass your password in the 'password' header for all POST/PUT/DELETE requests.",
        "endpoints": {
            "POST /api/rest": {
                "description": "Upload a file.",
                "form_data": {
                    "file": "(Required) The file to upload.",
                    "slug": "(Optional) Custom URL slug.",
                    "title": "(Optional) File title.",
                    "thumbnail": "(Optional) Thumbnail URL.",
                    "format": "(Optional) 'json' (default) or 'redirect'. If 'redirect', returns a 308 to the file."
                }
            },
            "PUT /api/rest/{slug}": {
                "description": "Update metadata for an existing file.",
                "form_data": {"slug": "New slug", "title": "New title", "thumbnail": "New thumbnail URL"}
            },
            "DELETE /api/rest/{slug}": {
                "description": "Delete a file permanently."
            }
        },
        "errors": {
            "401": "Unauthorized - Password missing or incorrect.",
            "404": "File or endpoint not found.",
            "409": "Slug already exists."
        }
    }

@app.post("/api/rest")
async def rest_upload(
    file: UploadFile = File(...),
    slug: str = Form(None),
    title: str = Form(""),
    thumbnail: str = Form(""),
    format: str = Form("json"),
    token: str = Depends(verify_auth)
):
    history = get_history()
    
    # Auto-generate slug if not provided
    final_slug = slug if slug else str(uuid.uuid4())[:8]
    
    # Check if slug exists
    if any(item["slug"] == final_slug for item in history):
        raise HTTPException(status_code=409, detail="Slug already in use")

    filename = file.filename
    repo_path = f"files/{final_slug}_{filename}"
    temp_path = f"/tmp/{filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    api.upload_file(path_or_fileobj=temp_path, path_in_repo=repo_path, repo_id=DATASET_REPO, repo_type="dataset")
    os.remove(temp_path)
    
    file_record = {
        "slug": final_slug, "filename": filename, "path": repo_path,
        "title": title or filename, "thumbnail": thumbnail
    }
    history.append(file_record)
    save_history(history)
    
    if format.lower() == "redirect":
        return RedirectResponse(url=f"/f/{final_slug}", status_code=308)
    
    return {"message": "Success", "data": file_record, "url": f"/f/{final_slug}"}

@app.put("/api/rest/{current_slug}")
async def edit_file(
    current_slug: str,
    new_slug: str = Form(None),
    title: str = Form(None),
    thumbnail: str = Form(None),
    token: str = Depends(verify_auth)
):
    history = get_history()
    for item in history:
        if item["slug"] == current_slug:
            if new_slug and new_slug != current_slug:
                if any(x["slug"] == new_slug for x in history):
                    raise HTTPException(status_code=409, detail="New slug already exists")
                item["slug"] = new_slug
            if title is !== None: item["title"] = title
            if thumbnail is !== None: item["thumbnail"] = thumbnail
            
            save_history(history)
            return {"message": "Updated", "data": item}
            
    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/api/rest/{slug}")
async def delete_file(slug: str, token: str = Depends(verify_auth)):
    history = get_history()
    file_record = next((item for item in history if item["slug"] == slug), None)
    
    if file_record:
        api.delete_file(path_in_repo=file_record["path"], repo_id=DATASET_REPO, repo_type="dataset")
        history = [item for item in history if item["slug"] != slug]
        save_history(history)
        return {"message": "Deleted"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/history")
async def fetch_history(token: str = Depends(verify_auth)):
    return get_history()

# --- Public File Serving ---
@app.get("/f/{slug}")
async def serve_public_file(slug: str):
    history = get_history()
    file_record = next((item for item in history if item["slug"] == slug), None)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
        
    file_path = hf_hub_download(repo_id=DATASET_REPO, filename=file_record["path"], repo_type="dataset", token=HF_TOKEN)
    return FileResponse(file_path, filename=file_record["filename"])