---
title: Qlynk Storage Node
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
pinned: true
license: mit
thumbnail: >-
  https://cdn-uploads.huggingface.co/production/uploads/6820305a563dbc18490b0f2f/qUx3-yyReb5Tzbnx5IFwQ.png
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

Bhai, tera `footer-extras.js` maine check kar liya! Usme tere saare social media aur project links (Instagram, GitHub, Discord, YouTube, Wiki, aur Study Clock) diye hue hain. 

In sabhi links ke liye **308 Permanent Redirect** routes banana bohot aasan hai. Tujhe bas apne `main.py` file mein, jahan tere baaki UI/Static routes hain (sabse niche `@app.get("/")` se theek upar), ye naya code block paste karna hai.

### 1. `main.py` mein ye code add kar:

```python
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
```

Is code ko daalne ke baad, jab bhi koi `teri-website.com/instagram` hit karega, toh backend usko direct tere original URL par 308 (Permanent Redirect) kar dega, jo SEO ke liye bhi best hota hai.

---

### 2. Markdown Table (Tere saare Routes aur Links)

Ye rahi tere saare redirect links ki summary table:

| Route Path | Redirect Type | Target Destination URL |
| :--- | :---: | :--- |
| `/instagram` | `308 Permanent` | [https://www.instagram.com/deepdey.official](https://www.instagram.com/deepdey.official) |
| `/github` | `308 Permanent` | [https://github.com/deepdeyiitgn](https://github.com/deepdeyiitgn) |
| `/discord` | `308 Permanent` | [https://discord.com/invite/t6ZKNw556n](https://discord.com/invite/t6ZKNw556n) |
| `/youtube` | `308 Permanent` | [https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/](https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/) |
| `/wiki` | `308 Permanent` | [https://qlynk.vercel.app/wiki](https://qlynk.vercel.app/wiki) |
| `/clock` | `308 Permanent` | [https://clock.qlynk.me](https://clock.qlynk.me) |

Bas ye routes apne `main.py` mein add karke update kar de, sab kuch perfectly redirect hone lagega!

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