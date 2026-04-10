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


---

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


http://googleusercontent.com/immersive_entry_chip/0

Note: Using format=redirect will respond with a 308 Permanent Redirect straight to the raw file, perfect for seamless frontend integrations.

---

## 👁️ Titan-Class Omniscient Telemetry (`/status`)

The Qlynk Storage Node includes a "God-Mode" real-time datacenter monitoring dashboard accessible at `/status`. Built natively via WebSockets, this is a full-scale hardware and network postmortem engine (Over 700+ lines of custom telemetry architecture).

**🔒 Omniscient Security Lock:** To view sensitive server data (Container Logs, Server IPs, Active Resource Hogs), you must be authenticated with the master `SPACE_PASSWORD` cookie via the main UI. Unauthenticated users receive a restricted, visually locked "Guest" view.

**🔥 Core Features of the Telemetry Dashboard:**
* 🌍 **Network Identity & Link Condition:** Tracks Server Host Region, Server External IP, and Your Client IP. Calculates real-time Client/Server Ping, Jitter (ms), and analyzes the route quality (Optimal vs. Poor).
* 🖧 **Deep Hardware Postmortem:** Bypasses standard outputs to read direct `/proc/cpuinfo` for exact CPU Model, Vendor, L-Cache, and Microcode. Includes `nvidia-smi` extraction for GPU Model, Temp, and Memory mapping.
* ⚙️ **Per-Core Engine Analytics:** Maps total system load and provides individual logical thread analysis including real-time processing percentages and CPU Frequency (MHz).
* ☁️ **Cloud Quota & Storage I/O:** Tracks live RAM consumption, Root Disk Read/Write speeds (MB/s), and dynamically tracks your Hugging Face Datasets capacity (Calculating exact GB available out of the 50GB limit).
* 📡 **Bandwidth & API Matrix:** Real-time Server Download/Upload speeds (KB/s), total outbound transfers, and an Endpoint Matrix tracking the live latency (ms) of specific microservices like the "REST Upload Engine" and "CDN File Stream".
* 🔥 **Top Resource Hogs:** Live `psutil` tracking table identifying the exact names, CPU %, and RAM % of the top 5 heaviest processes running on the server.
* 🚀 **Secure Log Streaming:** Direct SSE (Server-Sent Events) interception displaying Hugging Face Container Run Logs and Image Build Logs in a massive landscape dual-terminal view.
* 💾 **Export Subsystem:** Instantly audit and download the live telemetry payload. Export data in one click to **PDF, PNG Snapshot, Markdown, or Raw JSON**.
* 📱 **Fully Responsive UI:** Engineered with complex CSS grids to flawlessly scale from Ultra-Wide monitors down to mobile devices without breaking the matrix layout.

---

## ⚖️ Legal & Fair Use Disclaimer

**QLYNK Storage Node** is a proof-of-concept architecture developed strictly for **educational purposes**, backend API experimentation, and personal workflow automation. 

The inclusion of media extraction engines (such as `yt-dlp` and `FFmpeg`) is intended solely for processing royalty-free, public domain, or user-owned content. 

* 🚫 **No Endorsement of Piracy:** The developer (Deep Dey) strictly prohibits and does not endorse, encourage, or facilitate the downloading of copyrighted material without explicit permission from the rightful copyright owners.
* 👤 **End-User Responsibility:** By forking, deploying, or using this system, **YOU** assume full legal responsibility for the data and media you process. You must ensure full compliance with the Terms of Service of third-party platforms and your local copyright laws.
* 🛡️ **Zero Liability:** The creator of this repository assumes **NO LIABILITY** for any misuse of this software, account terminations, or copyright infringements committed by users operating their own private instances of this code.

---
---
---
### README IMPORTANT:

---
---
# 🚀 Qlynk Node Master (V09.04.2026 Enterprise Edition)

![Version](https://img.shields.io/badge/Version-2.0.0_Enterprise-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet.svg)
![Status](https://img.shields.io/badge/Status-On_Hiatus_(JEE_Prep)-orange.svg)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green.svg)
![License](https://img.shields.io/badge/License-Custom_Dual-red.svg)

> 💡 **Tip:** Press Ctrl+F (or Cmd+F) to search this documentation quickly.

**Qlynk Node Master** is an enterprise-grade, highly secure private cloud storage and streaming datacenter. Engineered to run entirely on Hugging Face Spaces (Free Tier), it acts as a self-sustaining media vault with an integrated Telegram ingestion bot, dynamic anti-hacker defenses, and a cinematic web player.

**Built by Deep Dey** (12th Grader & JEE Aspirant) 👨‍💻

---

> ⚠️ **PROJECT STATUS: ACTIVE DEVELOPMENT PAUSED (Effective April 9, 2026)**
> 
> *As of 09.04.2026 (1:20-22 PM IST), all active updates, feature additions, and bug fixes for Qlynk Node Master have been officially stopped.* > *I am currently in the 12th grade, and I am pausing all my software development projects to dedicate 100% of my focus to my upcoming Annual Exams and my preparation for the JEE Advanced. The goal is IIT Kharagpur CSE. The codebase provided here is stable and enterprise-ready. Thank you to everyone who supported this architecture!*

---

## 📖 The Story & The Architect

### 🏢 About This Project (The Qlynk Ecosystem)
Qlynk Node Master was born out of a simple engineering challenge: *Can we build a limitless, highly secure SaaS ecosystem without paying for traditional cloud storage?* Today, it stands as an autonomous datacenter.
* **The Architecture:** It seamlessly merges a high-speed FastAPI backend with an asynchronous Pyrogram Telegram ingestion engine. It uses Hugging Face Spaces (Free Tier) as a massive, synchronized file vault.
* **The Scale:** From automatically converting MKV to MP4 using background FFmpeg threads, to processing payments via Razorpay and auto-generating PDF invoices with SVG logos, the entire pipeline is fully self-sustaining.
* **The UI/UX:** Everything is controlled via a desktop-enforced Virtual Master OS (Dashboard) that features native Universal Previews for media/code, bulk data wiping, and granular token session management.

### 👨‍💻 About Me (The Developer)
I am an aspiring software engineer and full-stack developer based in Tripura, India. I specialize in designing scalable cloud architectures, high-performance web servers, and automated digital infrastructure.
* **The Academic Mission:** I am currently in **Class 12**. While I have spent over three years mastering AI, system architecture, and full-stack development, my ultimate goal right now is to crack the **JEE Advanced** and secure a seat in Computer Science Engineering (CSE) at **IIT Kharagpur**.
* **My Arsenal:** My technical stack includes Python, TypeScript, FastAPI, Pyrogram, modern cloud environments (Vercel, Render), database management, and implementing advanced API security protocols.
* **The Current Status:** I have officially placed all my software development projects on a strict hiatus to dedicate 100% of my analytical thinking and problem-solving skills toward Physics, Chemistry, and Mathematics for my upcoming board exams and JEE.


---

## ✨ Enterprise Features
- **🤖 Omniscient Telegram Engine:** Upload directly via Telegram. Features an asynchronous queue system (`asyncio.Lock`) to prevent server crashes, automatic MKV to MP4 optimization via FFmpeg, and native thumbnail extraction.
- **🛡️ Secure Tokenized Streaming:** Original file URLs are never exposed. The system uses dynamic, time-limited tokens with a 4-hour "Rolling Expiry" to prevent piracy and direct downloads (IDM blocks).
- **🕸️ Anti-Hacker Tarpit (Honeypot):** Brute-force protection that feeds fake garbage bytes to unauthorized scrapers/bots while giving them a `200 OK` status, effectively wasting their time and bandwidth.
- **🎬 Cinematic Media Tube:** A beautiful, responsive web player with custom visualizers, auto-subtitle conversion (SRT to VTT), Playback Speed controls, Picture-in-Picture (PiP), and Spacebar shortcuts.
- **📊 God-Mode Telemetry:** Real-time WebSockets-powered dashboard (`/status`) showing core-by-core CPU usage, RAM pool, Network I/O, API latencies, and HF Cloud Quota.
- **♾️ 24/7 Self-Sustaining:** An automated anti-sleep background ping system keeps the HF container alive infinitely.
- **💳 SaaS Checkout Engine:** Built-in Razorpay payment gateway to sell premium streaming tokens. Features anti-spam rate limiting and automatic PDF invoice generation with SVG logos.
- **🎧 AI Helpdesk & Support System:** An isolated ticketing system running via Telegram. Users can raise tickets, talk to an automated AI bot (FAQ matching), or request human admin support directly through the dashboard.
- **⏳ Dual-Auth & Token Vault:** Advanced time-limited share tokens (Basic, Pro, Ultra) with cryptographic signature verification. Generates auto-expiring secure links.
- **🖥️ Virtual Master OS (Admin Dashboard):** A desktop-enforced, highly secured GUI panel to manage the entire datacenter. Includes bulk file wiping, custom token forging (with precise user/session limits), session killing, and live server vitals.
- **👁️ Universal Preview Engine & Native Rendering:** Built directly into the dashboard, a dark-mode modal seamlessly renders videos, audio, images, and code/text files without opening new tabs. Additionally, WebP, SVG, and GIF formats are natively forced to render inline in browsers with auto-generated thumbnails.
* 🏢 **Intelligent Role-Based Routing (RBAC):** The core engine dynamically reads cryptographic cookies to differentiate between the Master Admin, Premium Guests, and Public Users. It flawlessly serves raw media for Admin Dashboard previews while automatically routing public users to the frontend cinematic player.
* 💼 **Autonomous Premium SaaS Delivery:** Built-in support for "Guest Share Tokens." When customers purchase access, the architecture seamlessly grants them the same high-security 4-hour streaming privileges as the admin, allowing the datacenter to function as an automated commercial streaming platform.

---

## 🔒 Security & Cryptography (Military-Grade Protections)
This architecture is fortified with advanced cybersecurity protocols designed to defeat scrapers, brute-force bots, and unauthorized access attempts.

- **🕸️ The Honeypot (Tarpit) Architecture:** Instead of returning a standard `404 Not Found` for invalid links, the server intercepts unauthorized bots and returns a `200 OK` status while feeding them an infinite loop of generated garbage bytes. This actively exhausts the bot's bandwidth and RAM without consuming actual server storage.
- **🔄 Moving Target Defense (Dynamic Slug Rotator):** A background chron-job autonomously triggers every 6 to 24 hours to entirely wipe and regenerate new 32-character Hex URLs for all files in the database. This makes link-scraping mathematically impossible while safely preserving all internal subtitle and thumbnail linkages.
- **🛡️ WAF & Exponential Backoff (Fail2Ban Logic):** The API is protected by a self-healing IP rate-limiter. If an IP guesses incorrect links repeatedly, they are shadow-banned for 10 minutes, then 30 minutes, and so on. If a legitimate user makes a typo but subsequently enters a valid link, their penalty is instantly reset to zero.
- **⏳ Cryptographic Token Vault:** Original Hugging Face repository paths are permanently hidden. The system generates secure, time-bound access tokens (Basic, Pro, Ultra) with cryptographic signatures. These tokens have a "Rolling Expiry" (e.g., 4 hours) and strict anti-IDM (Internet Download Manager) headers to completely block piracy and direct downloading.
* **🛡️ Smart Cookie Firewall (Anti-IDOR):** Raw CDN file routes are cryptographically shielded. Public scrapers or Download Managers attempting direct access are instantly intercepted and 302-redirected to the secure cinematic player, ensuring 100% piracy protection.
* **🔑 Dual-Auth Tokenized Streaming:** The streaming API seamlessly supports both Admin Master Cookies and rolling Guest Share Tokens, ensuring premium customers get uninterrupted access while public access is firmly denied (HTTP 401).

---
---

## 🛠️ How to Deploy (Build Your Own Enterprise Node)

This architecture is strictly designed to run natively on **Hugging Face Spaces (Docker SDK)**. You do not need an external VPS or paid cloud hosting. Follow these precise steps to deploy your own autonomous media vault:

### Step 1: Create the Storage Vault (Database)
The architecture uses Hugging Face Datasets as a limitless, zero-cost private database.
1. Go to [Hugging Face Datasets](https://huggingface.co/datasets) and click **Create new Dataset**.
2. Name it (e.g., `qlynk-storage-vault`).
3. **CRITICAL:** Set the visibility to **Private** to ensure your data and `history.json` remain completely secure.
4. Note down the Repository ID (Format: `your-username/qlynk-storage-vault`).

### Step 2: Create the Main Server (Node)
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces) and click **Create new Space**.
2. Name your space (e.g., `qlynk-node-master`).
3. Select **Docker** as the Space SDK and choose the **Blank** template.
4. Keep the Space hardware on the **Free Tier** (The architecture is optimized to run flawlessly on basic hardware).

### Step 3: Configure Environment Secrets
Before pushing the code, you must configure the Master Keys. Go to your Space's **Settings -> Variables and secrets -> Secrets** and add the following mandatory keys:

| Secret Name | Description |
|---|---|
| `HF_TOKEN` | Your Hugging Face Access Token. It **MUST** have `WRITE` permissions. |
| `DATASET_REPO` | The exact ID of the dataset you created in Step 1 (e.g., `username/dataset-name`). |
| `SPACE_PASSWORD` | A strong master password. This unlocks the Virtual OS (`/dashboard`). |
| `TG_API_ID` | Your Telegram API ID (Get this from my.telegram.org). |
| `TG_API_HASH` | Your Telegram API Hash. |
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token (Get from @BotFather). |
| `AUTO_SLUG_ROTATOR` | Set to `false` to disable dynamic URL rotation. Useful if you want to use Qlynk as a permanent CDN for your website's profile pictures or CSS assets. Default is `true`. |

**Optional Enterprise Secrets (For Monetization):**
| Secret Name | Description |
|---|---|
| `CHECKOUT_TOGGLE` | Set this to exactly match your `SPACE_PASSWORD` to activate the Razorpay SaaS Checkout UI. |
| `RAZORPAY_KEY_ID` | Your Razorpay API Key ID. |
| `RAZORPAY_KEY_SECRET`| Your Razorpay API Secret. |
| `PROXY_URL` | Proxy URL if Hugging Face IPs get blocked by external media scraping sources. |

### Step 4: Clone & Push the Architecture
Open your terminal or command prompt. You will pull the code directly from this GitHub repository and push it to your Hugging Face Space.

```bash
# 1. Clone this repository to your local machine
git clone [https://github.com/deepdeyiitgn/static-files.git](https://github.com/deepdeyiitgn/static-files.git)
cd static-files

# 2. Add your Hugging Face Space as a remote origin
# Replace YOUR_USERNAME and YOUR_SPACE_NAME with your actual HF details
git remote add hf [https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME](https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME)

# 3. Push the entire architecture to Hugging Face
git push hf main
```

Once pushed, Hugging Face will automatically read the Dockerfile, build the secure container, and execute the start.sh bootloader. Within 2-3 minutes, your Enterprise Node will be fully operational. You can then navigate to https://hf.space/.../dashboard to access the Virtual OS.

---
---

## 📂 Project Structure & Main Code
Here is where the core logic lives:
- `main.py`: The heart of the project. Contains the FastAPI server, Media Routing, Token Streaming, Telegram Bot logic, and the Web UI / Dashboard HTML.
- `bot.py`: The background organic ping system that prevents the server from sleeping.
- `start.sh`: The bootloader script that starts both the `bot.py` and the `uvicorn` FastAPI server.
- `history.json`: (Generated at runtime) The central database saving all your file metadata securely on Hugging Face Datasets.

---

## 🛠️ How to Build Your Own Server (Deployment)

You can easily deploy your own private streaming node on Hugging Face Spaces for free!

### Step 1: Create a Hugging Face Space
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces) and click **Create new Space**.
2. Name your space (e.g., `my-private-vault`).
3. Choose **Docker** as the Space SDK and select **Blank**.
4. Set the space hardware to **Free**.

### Step 2: Set up Environment Variables (Secrets)
Go to your Space's **Settings -> Variables and secrets -> Secrets** and add the following:

| Variable Name | Description |
|---|---|
| `HF_TOKEN` | Your Hugging Face Access Token (Must have **WRITE** permissions). |
| `SPACE_PASSWORD` | A strong password to unlock your Web UI & Dashboard. |
| `TG_API_ID` | Your Telegram API ID (get from my.telegram.org). |
| `TG_API_HASH` | Your Telegram API Hash. |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather on Telegram. |
| `TG_SESSION_STRING` | *(Optional)* Pyrogram session string to unlock true 2GB file upload limits. |
| `PROXY_URL` | *(Optional)* Proxy URL if your datacenter IP gets blocked by external sites. |
| `CHECKOUT_TOGGLE` | Set this to match your SPACE_PASSWORD to enable the Razorpay Checkout UI. |
| `RAZORPAY_KEY_ID` | Your Razorpay API Key for the payment gateway. |
| `RAZORPAY_KEY_SECRET` | Your Razorpay API Secret. |
| `YT_COOKIES` | (Optional) YouTube cookies in Netscape format to bypass age-restrictions or blockades. |
| `DOMAIN_1`, `DOMAIN_2` | (Optional) Whitelist specific domains for CORS (e.g., `https://mywebsite.com`). |
| `AUTO_SLUG_ROTATOR` | Set to `false` to disable dynamic URL rotation. Useful if you want to use Qlynk as a permanent CDN for your website's profile pictures or CSS assets. Default is `true`. |

### Step 3: Clone and Push the Code
Clone this repository to your local machine and push it to your newly created Hugging Face Space:
```bash
git clone [https://github.com/deepdeyiitgn/static-files.git](https://github.com/deepdeyiitgn/static-files.git)
cd static-files
git remote add hf [https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME](https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME)
git push -u hf main
```
Your server will start building. Once the status says "Running", your private vault is ready!

---

## 🆘 Emergency Troubleshooting & Node Diagnostics

*Is your datacenter node acting up? Before raising a support ticket, consult this rapid-response diagnostic matrix.*

> 🛑 **1. FATAL: Git Exit Code 128 (Build Failure)**
> * **Symptom:** Hugging Face Space fails to build or fetch the repository.
> * **Diagnosis:** Binary file clash in version control (usually caused by compiled `.pyc` files).
> * **Fix:** Delete the `__pycache__` folder from your local machine, add `__pycache__/` to your `.gitignore`, commit, and push again. Alternatively, click **Factory Rebuild** in HF Space Settings.

> 🔌 **2. ERROR 500: Internal Server Error on Boot**
> * **Symptom:** The FastAPI server crashes immediately upon opening the URL.
> * **Diagnosis:** Missing or misconfigured Environment Secrets.
> * **Fix:** Ensure `DATASET_REPO` is correctly typed (`username/repo-name`) and your `HF_TOKEN` has strictly **WRITE** permissions.

> 🐢 **3. NETWORK: YouTube/Instagram Links Failing (Falling back to 308)**
> * **Symptom:** Sending external links to the bot results in an error or fallback redirect.
> * **Diagnosis:** The Hugging Face Datacenter IP is temporarily rate-limited or blocked by the target platform (YouTube/Meta).
> * **Fix:** Add a fresh, rotating proxy URL to the `PROXY_URL` environment secret to bypass the firewall.

> 🤖 **4. BOT: Unresponsive to `/index` or `/connect`**
> * **Symptom:** The Pyrogram bot ignores commands in a specific channel.
> * **Diagnosis:** Missing permissions or wiped memory cache.
> * **Fix:** Make sure the bot is an **Admin** in the target channel. If the database was recently wiped, manually forward *one* message from that channel to the bot so it can learn the Chat ID, then try again.

> 📱 **5. ACCESS: Mobile Dashboard is Locked/Blocked**
> * **Symptom:** Opening `/dashboard` on a phone shows a Security Lock screen.
> * **Diagnosis:** Expected behavior. The Master OS is dense with data tables and admin controls.
> * **Fix:** This is a security and UX enforcement. Please access the Master OS terminal strictly from a **Desktop or Laptop browser**.

---

## ❓ The Omniscient Knowledge Base (50 FAQs)

*Click on any question below to reveal the detailed answer.*

### 🏛️ Core Architecture & Hosting

<details>
<summary><b>1. What exactly is Qlynk Node Master?</b></summary>
<blockquote>
It is a self-sustaining, enterprise-grade private cloud storage and media streaming ecosystem built entirely on Hugging Face Spaces, acting as a zero-cost decentralized datacenter.
</blockquote>
</details>

<details>
<summary><b>2. Do I need to pay for AWS, GCP, or any VPS hosting?</b></summary>
<blockquote>
<b>No.</b> The architecture is mathematically engineered to exploit Hugging Face's free Docker SDK tier and free Datasets, giving you a powerful backend without traditional server costs.
</blockquote>
</details>

<details>
<summary><b>3. Is my uploaded data public to the world?</b></summary>
<blockquote>
<b>No.</b> If you configure your Hugging Face Dataset visibility to "Private" as instructed, nobody can access your raw files, database, or API without your strict cryptographic tokens.
</blockquote>
</details>

<details>
<summary><b>4. What programming languages power this engine?</b></summary>
<blockquote>
The backend is driven by asynchronous <b>Python 3.10+</b> (FastAPI & Pyrogram), while the frontend UI and Cinematic Player are built with raw HTML, CSS, and Vanilla JavaScript for maximum speed.
</blockquote>
</details>

<details>
<summary><b>5. Can I use a Custom Domain (like mywebsite.com)?</b></summary>
<blockquote>
<b>Yes.</b> You can easily map a custom domain to your Hugging Face Space using Cloudflare proxy or Vercel edge functions.
</blockquote>
</details>

<details>
<summary><b>6. What happens if the Hugging Face Space goes to sleep?</b></summary>
<blockquote>
Free tier Spaces pause after inactivity. However, the moment a request hits the URL or the Telegram Bot receives a message, the FastAPI server cold-boots in seconds and resumes normal operations.
</blockquote>
</details>

<details>
<summary><b>7. Why is there a Dual-License on this repository?</b></summary>
<blockquote>
To protect the Intellectual Property. The code is free for personal, educational, and testing use. However, commercial deployment or SaaS monetization requires a paid enterprise license from the original author.
</blockquote>
</details>

<details>
<summary><b>8. What does "System Hiatus" mean?</b></summary>
<blockquote>
The original architect (Deep Dey) is currently in the 12th grade and has locked the repository to focus 100% on the upcoming JEE Advanced examinations. No new features will be added during this period.
</blockquote>
</details>

<details>
<summary><b>9. How is the database managed without SQL?</b></summary>
<blockquote>
We use a highly optimized, asynchronous JSON document system (<code>history.json</code>, <code>tg_users.json</code>) that syncs natively with the Hugging Face Hub, bypassing the need for heavy SQL databases.
</blockquote>
</details>

<details>
<summary><b>10. Can I deploy this on Render or Heroku instead?</b></summary>
<blockquote>
While possible, the code relies heavily on the <code>huggingface_hub</code> Python library to write data to Datasets. You would need to heavily modify the storage logic to use AWS S3 or local disks if moving away from HF.
</blockquote>
</details>

### 🛡️ Military-Grade Security

<details>
<summary><b>11. What is the Honeypot (Tarpit) mechanism?</b></summary>
<blockquote>
If a scraper bot guesses random file URLs, our server doesn't return a "404 Not Found". Instead, it returns a "200 OK" and feeds the bot infinite garbage bytes, actively crashing the bot's RAM and wasting its bandwidth.
</blockquote>
</details>

<details>
<summary><b>12. Why do my file URLs change automatically?</b></summary>
<blockquote>
This is our <b>Moving Target Defense</b>. A background Cron-job rotates the 32-character URLs randomly every 6 to 24 hours to make systematic link scraping mathematically impossible.
</blockquote>
</details>

<details>
<summary><b>13. Can I turn off the dynamic URL rotation?</b></summary>
<blockquote>
<b>Yes.</b> Set the Environment Secret <code>AUTO_SLUG_ROTATOR = false</code>. This puts the node into "CDN Mode," keeping links permanent for hosting website assets like CSS or Profile Pictures.
</blockquote>
</details>

<details>
<summary><b>14. How does the IP Banning (Fail2Ban) work?</b></summary>
<blockquote>
If an IP hits the honeypot 20+ times, they are shadow-banned using an exponential backoff timer (10 mins, 30 mins, etc.). 
</blockquote>
</details>

<details>
<summary><b>15. What if a legitimate user makes a typo and gets banned?</b></summary>
<blockquote>
The system is self-healing. The moment the penalized IP successfully accesses a valid, real URL, their penalty strikes are instantly reset to zero.
</blockquote>
</details>

<details>
<summary><b>16. How is the Master Dashboard secured?</b></summary>
<blockquote>
The <code>/dashboard</code> route is protected by a strict Header/Cookie authentication system requiring the exact <code>SPACE_PASSWORD</code> defined in your environment variables.
</blockquote>
</details>

<details>
<summary><b>17. Can someone bypass the payment gateway to get tokens?</b></summary>
<blockquote>
<b>No.</b> The backend cryptographically verifies the Razorpay signature (Order ID + Payment ID + Secret) before generating and storing the secure token in the database.
</blockquote>
</details>

<details>
<summary><b>18. Are my Telegram messages end-to-end encrypted?</b></summary>
<blockquote>
Telegram's MTProto protocol secures the connection between you and the bot. The files are then downloaded to the container and uploaded to HF via HTTPS (TLS 1.2+).
</blockquote>
</details>

<details>
<summary><b>19. Why does the API return JSON by default?</b></summary>
<blockquote>
For enterprise interoperability. You can integrate this node directly into other frontends, mobile apps, or CLI tools seamlessly via the <code>/api/rest</code> endpoints.
</blockquote>
</details>

<details>
<summary><b>20. What prevents DDOS attacks on the API?</b></summary>
<blockquote>
The payment and checkout APIs are protected by an in-memory Rate Limiter (max 5 requests per minute per IP) to prevent fraudulent spam requests.
</blockquote>
</details>

<details>
<summary><b>20.1. Can users bypass the player and download videos directly using IDM or scripts?</b></summary>
<blockquote>
<b>No.</b> The node is protected by a <b>Smart Cookie Firewall (IDOR Protection)</b>. If a public user tries to reverse-engineer the URL and access the raw CDN file route (<code>/f/[slug]</code>) for a media file, the server detects the missing Admin cookie and instantly hits them with a 302 Redirect back to the secure cinematic player. 
</blockquote>
</details>

<details>
<summary><b>20.2. Do premium users (Guest Tokens) get the same streaming security as the Admin?</b></summary>
<blockquote>
<b>Yes.</b> The architecture dynamically verifies dual-auth cookies (Admin <code>auth_token</code> or Guest <code>share_token</code>). Premium users get seamless access to the tokenized 4-hour streaming endpoint, while unauthorized public requests are outright blocked with a 401 error.
</blockquote>
</details>

### 📤 Data Ingestion & Storage

<details>
<summary><b>21. What is the maximum file size I can upload?</b></summary>
<blockquote>
If you configure a Telegram UserBot session, you can upload up to <b>2GB</b> per file. Via the standard Web API or normal Bot Token, the limit is governed by Telegram's standard limits (50MB).
</blockquote>
</details>

<details>
<summary><b>22. What happens if I upload multiple files at once?</b></summary>
<blockquote>
The bot uses an <code>asyncio.Lock()</code> Queue System. It will acknowledge all files but strictly process and upload them one by one to prevent server RAM overflow and crashes.
</blockquote>
</details>

<details>
<summary><b>23. What is the <code>/batch</code> command?</b></summary>
<blockquote>
Activating batch mode tells the bot to expect a massive dump of files. It optimizes the queue and suppresses repetitive status updates to keep your chat clean.
</blockquote>
</details>

<details>
<summary><b>24. How do I upload files via YouTube or Instagram links?</b></summary>
<blockquote>
Just send the URL to the bot. The integrated <code>yt-dlp</code> engine will download the highest quality media, process it locally, and push it to your private HF Vault.
</blockquote>
</details>

<details>
<summary><b>25. What is the <code>/index</code> deep-scan bypass?</b></summary>
<blockquote>
Bots normally cannot read old channel history. The <code>/index</code> command forces the bot to crawl backwards through thousands of messages, map the media IDs, and save them to your database for instant searching.
</blockquote>
</details>

<details>
<summary><b>26. Can I upload non-media files like ZIPs or PDFs?</b></summary>
<blockquote>
<b>Yes.</b> The vault supports any MIME type. Non-media files will trigger a standard direct download when accessed via their secure links.
</blockquote>
</details>

<details>
<summary><b>27. What happens if my <code>history.json</code> is accidentally deleted?</b></summary>
<blockquote>
The FastAPI lifespan manager will detect the missing database on boot and automatically generate a fresh, empty JSON structure to prevent fatal crashes.
</blockquote>
</details>

<details>
<summary><b>28. How are thumbnails generated?</b></summary>
<blockquote>
For Telegram uploads, it extracts native Telegram thumbnails. For WebP/SVG uploads, it uses the image itself. For YouTube, it fetches the MaxRes thumbnail automatically.
</blockquote>
</details>

<details>
<summary><b>29. Where do the files actually live?</b></summary>
<blockquote>
In the "Files and versions" tab of the Hugging Face Dataset repository you connected during Step 1 of the deployment.
</blockquote>
</details>

<details>
<summary><b>30. Is there a storage limit on Hugging Face Datasets?</b></summary>
<blockquote>
Currently, Hugging Face offers practically limitless storage for Datasets, though massive usage (hundreds of Terabytes) might eventually trigger fair-use flags from their automated systems.
</blockquote>
</details>

### 🎬 Cinematic Streaming & Media

<details>
<summary><b>31. What makes the Web Player "Cinematic"?</b></summary>
<blockquote>
It features a dark-mode UI, dynamic dominant color extraction (the UI changes color based on the thumbnail), audio visualizers, and YouTube-style keyboard logic.
</blockquote>
</details>

<details>
<summary><b>32. Why do MKV/AVI files take longer to process?</b></summary>
<blockquote>
Browsers cannot stream MKV files natively. When uploaded, a background FFmpeg worker automatically converts MKV/AVI to MP4 and fixes audio to AAC format for flawless web playback.
</blockquote>
</details>

<details>
<summary><b>33. How does Tokenized Streaming work?</b></summary>
<blockquote>
Clicking "Secure Stream" generates a temporary token link (valid for 4 hours). This hides the original dataset URL and protects your bandwidth from direct download scraping.
</blockquote>
</details>

<details>
<summary><b>34. Can Internet Download Manager (IDM) steal the videos?</b></summary>
<blockquote>
<b>No.</b> The streaming endpoint uses strict `sec-fetch-dest` header inspection. If a request comes from an external downloader rather than a browser `<video>` tag, it is blocked with a 403 error.
</blockquote>
</details>

<details>
<summary><b>35. Does the video stop buffering if I pause for 4 hours?</b></summary>
<blockquote>
We use <b>Rolling Expiries</b>. Every time the video player requests a new chunk of data, the 4-hour token timer is automatically extended, ensuring long movies never crash mid-watch.
</blockquote>
</details>

<details>
<summary><b>36. How do I add Subtitles to a video?</b></summary>
<blockquote>
Open the Admin Dashboard, go to the vault, click "Add CC", and upload your <code>.srt</code> or <code>.vtt</code> file.
</blockquote>
</details>

<details>
<summary><b>37. Does the player support SRT subtitles?</b></summary>
<blockquote>
Browsers natively only support VTT. However, our server automatically converts your SRT files into VTT format <i>on-the-fly</i> before sending them to the browser!
</blockquote>
</details>

<details>
<summary><b>38. Can I adjust the subtitle size?</b></summary>
<blockquote>
<b>Yes.</b> While watching a video, press the <b>`+`</b> or <b>`-`</b> keys on your keyboard to scale the subtitle font size dynamically.
</blockquote>
</details>

<details>
<summary><b>39. Does the player have Picture-in-Picture (PiP)?</b></summary>
<blockquote>
<b>Yes.</b> You can click the PiP button or press the <b>`I`</b> key to pop the video out and browse other tabs while watching.
</blockquote>
</details>

<details>
<summary><b>40. How does the spacebar fast-forward work?</b></summary>
<blockquote>
Just like YouTube, if you press and hold the spacebar, the video speed doubles (2x) instantly. Release it, and it returns to normal speed.
</blockquote>
</details>

### 💼 SaaS Checkout & Administration

<details>
<summary><b>41. How do I enable the Razorpay Checkout?</b></summary>
<blockquote>
Set the <code>CHECKOUT_TOGGLE</code> environment secret to exactly match your <code>SPACE_PASSWORD</code>. This activates the <code>/checkout</code> route for public users.
</blockquote>
</details>

<details>
<summary><b>42. What do users receive after a successful payment?</b></summary>
<blockquote>
They immediately receive a cryptographic access token displayed on the screen, and the server generates a personalized PDF Receipt (with your logo) and sends it to their Telegram.
</blockquote>
</details>

<details>
<summary><b>43. Can users log in to multiple devices with one token?</b></summary>
<blockquote>
The Token Forge allows you to set concurrent login limits (e.g., max 2 active sessions). If they exceed this, access is denied.
</blockquote>
</details>

<details>
<summary><b>44. How does the AI Helpdesk (<code>/support</code>) work?</b></summary>
<blockquote>
Users type <code>/support</code> in the bot. The AI checks their query against your <code>support_faq.json</code>. If a match is found, it replies instantly. If not, it generates a ticket for Human Support.
</blockquote>
</details>

<details>
<summary><b>45. How do I reply to support tickets?</b></summary>
<blockquote>
As an admin, you will receive a notification with "Accept" or "Reject" buttons. Clicking "Accept" connects your chat directly to the user, masking your identity as "Admin".
</blockquote>
</details>

<details>
<summary><b>46. What is the Virtual Master OS?</b></summary>
<blockquote>
It is the highly-secured <code>/dashboard</code> route. It acts as a desktop-grade operating system to monitor server health, manage files, and revoke user tokens.
</blockquote>
</details>

<details>
<summary><b>47. What does "Clear Active Sessions" do in the dashboard?</b></summary>
<blockquote>
If you suspect a user is sharing their token with friends, clicking this button instantly changes the token's cryptographic salt, forcing all currently watching devices to be logged out.
</blockquote>
</details>

<details>
<summary><b>48. What is the Universal Preview Engine?</b></summary>
<blockquote>
Instead of downloading files to check what they are, clicking a thumbnail in the Dashboard opens a dark-mode modal that natively plays videos, audio, images, or displays text/code directly.
</blockquote>
</details>

<details>
<summary><b>49. Can I bulk delete files?</b></summary>
<blockquote>
<b>Yes.</b> The Dashboard allows you to select multiple files via checkboxes and execute a bulk wipe, permanently deleting them from the Hugging Face dataset.
</blockquote>
</details>

<details>
<summary><b>50. How accurate is the "Server Health" tab?</b></summary>
<blockquote>
It uses high-precision telemetry middleware (`time.perf_counter()`) to track real-time API latencies, CPU/RAM limits, and Honeypot metrics directly from the Docker container.
</blockquote>
</details>

---

## ⚖️ Legal Disclaimers & Fair Use Warnings

**⚠️ Regarding `yt-dlp` and Media Extraction:**
This project utilizes the `yt-dlp` library solely as a technical demonstration of media routing and extraction architectures. 
- This software is strictly for **Personal, Educational, and Archival purposes only**.
- Do not use this tool to pirate, distribute, or infringe upon copyrighted material. 
- The creator (Deep Dey) holds absolutely no liability for how users choose to utilize this software or the content they process through it. You are solely responsible for complying with the Terms of Service of any platform you interact with.

**⚠️ Copyright & Licensing Rules (Dual-License Model):**
This repository operates under a **Strict Attribution & Non-Commercial Custom License**. 

1. **Free for Learning:** You are free to fork, read, and deploy this architecture strictly for **Personal, Educational, or Testing purposes**.
2. **No White-labeling:** You **CANNOT** remove, modify, or hide the attribution, developer credits (Deep Dey / Qlynk), or original copyright notices present in the code, UI, or Footer.
3. **COMMERCIAL USE IS STRICTLY PROHIBITED:** Enterprise deployment, use in production environments, or integration into monetized SaaS projects is **NOT permitted** under this free license. 
4. **Enterprise License:** If you represent a company or wish to use this architecture for commercial purposes to generate revenue, you must obtain a separate **Paid Commercial License** directly from the author. Contact me to discuss commercial deployment.

---

<!-- ### 🌟 Support the Developer
If you found this architecture helpful or learned something new about API security and Python web servers, please give this repository a **⭐ Star**!  -->

### 🌟 Final Note from the Developer
Building Qlynk Node Master and taking it to an Enterprise SaaS level has been an incredible engineering journey. If you found this architecture helpful or learned something new about API security, rate-limiting, and Python web servers, please give this repository a **⭐ Star**! 

*Signing off for now. Dreaming of IIT Kharagpur CSE. Keep coding, keep building!* 🚀📚

---
<p align="center">
  <i>📅 <b>Last System Update (Hiatus Locked):</b> Friday, 10 April 2026 | 01:24 PM IST (GMT+05:30)</i><br>
  <i>🔒 Architecture completely locked and deployed.</i>
</p>
