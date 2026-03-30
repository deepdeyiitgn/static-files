---
title: Qlynk Storage Node
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# 🚀 Ultimate Private File Hosting System

A highly secure, Dockerized FastAPI application built to use Hugging Face Datasets as a bottomless storage bucket. 

**Features:**
- ♾️ **No File Limits:** Bypass standard hosting limits (Supports up to HF's total repo limit of 50GB).
- 🍪 **Persistent Login:** Master password creates a cookie. No need to login every time.
- ⚙️ **Fully Featured REST API:** Use `/api/rest` externally with your websites.
- 🔀 **308 Smart Redirects:** Upload a file and instantly redirect users to it via API.
- ✏️ **Metadata Management:** Edit Slugs, Titles, and Thumbnails on the fly.
- 🔒 **Domain Whitelisting (CORS):** Restrict access strictly to your own websites.

---

## 🛠️ How to Deploy / Fork this Space

You can fork this space to create your own personal hosting node. **You don't even need to create a dataset manually!** The code automatically detects your username and creates a private dataset for you.

### 1. Fork the Repo
Click the **"Duplicate this Space"** button on Hugging Face.

### 2. Set up Environment Variables (Secrets)
Go to your new Space's **Settings** -> **Variables and secrets** and add these Secrets:

| Variable Name | Description |
| :--- | :--- |
| `HF_TOKEN` | Your HF Access Token (Must have **Write** permissions). *Required*. |
| `SPACE_PASSWORD` | The master password you want to use for the dashboard and API. *Required*. |
| `DOMAIN_1` | (Optional) Whitelist a domain for CORS (e.g., `https://qlynk.me`). |
| `DOMAIN_2` | (Optional) Add as many domains as you want by numbering them `DOMAIN_3`, `DOMAIN_4` etc. |

*Once you add the tokens and restart the space, it will automatically create a private dataset named `my-private-storage` in your account!*

---

## 💻 REST API Usage

Hit the `/api/rest` endpoint via a `GET` request in your browser to see the full JSON documentation, or use the reference below:

### Upload a file via API (cURL Example)
```bash
curl -X POST "https://YOUR_SPACE_URL/api/rest" \
  -H "password: YOUR_SPACE_PASSWORD" \
  -F "file=@/path/to/your/image.png" \
  -F "slug=my-custom-url" \
  -F "title=My Cool Image" \
  -F "format=redirect"

Note: Using format=redirect will respond with a 308 Permanent Redirect straight to the raw file, perfect for seamless frontend integrations.