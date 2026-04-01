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

```NOTE: I Recommend You To Run On Local So Yt-dlp Works Correctly```

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

### 2. Markdown Table (All Social Links)

| Route Path | Redirect Type | Target Destination URL |
| :--- | :---: | :--- |
| `https://static.qlynk.me/instagram` | `308 Permanent` | [https://www.instagram.com/deepdey.official](https://www.instagram.com/deepdey.official) |
| `https://static.qlynk.me/github` | `308 Permanent` | [https://github.com/deepdeyiitgn](https://github.com/deepdeyiitgn) |
| `https://static.qlynk.me/discord` | `308 Permanent` | [https://discord.com/invite/t6ZKNw556n](https://discord.com/invite/t6ZKNw556n) |
| `https://static.qlynk.me/youtube` | `308 Permanent` | [https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/](https://youtube.com/channel/UCrh1Mx5CTTbbkgW5O6iS2Tw/) |
| `https://static.qlynk.me/wiki` | `308 Permanent` | [https://qlynk.vercel.app/wiki](https://qlynk.vercel.app/wiki) |
| `https://static.qlynk.me/clock` | `308 Permanent` | [https://clock.qlynk.me](https://clock.qlynk.me) |

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
```

Note: Using format=redirect will respond with a 308 Permanent Redirect straight to the raw file, perfect for seamless frontend integrations.

---

## ⚖️ Legal & Fair Use Disclaimer

**QLYNK Storage Node** is a proof-of-concept architecture developed strictly for **educational purposes**, backend API experimentation, and personal workflow automation. 

The inclusion of media extraction engines (such as `yt-dlp` and `FFmpeg`) is intended solely for processing royalty-free, public domain, or user-owned content. 

* 🚫 **No Endorsement of Piracy:** The developer (Deep Dey) strictly prohibits and does not endorse, encourage, or facilitate the downloading of copyrighted material without explicit permission from the rightful copyright owners.
* 👤 **End-User Responsibility:** By forking, deploying, or using this system, **YOU** assume full legal responsibility for the data and media you process. You must ensure full compliance with the Terms of Service of third-party platforms and your local copyright laws.
* 🛡️ **Zero Liability:** The creator of this repository assumes **NO LIABILITY** for any misuse of this software, account terminations, or copyright infringements committed by users operating their own private instances of this code.

---