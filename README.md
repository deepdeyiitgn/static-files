# 🚀 Qlynk Node Master (V09.04.2026 Enterprise Edition)

![Version](https://img.shields.io/badge/Version-2.0.0_Enterprise-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet.svg)
![Status](https://img.shields.io/badge/Status-On_Hiatus_(JEE_Prep)-orange.svg)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green.svg)
![License](https://img.shields.io/badge/License-Custom_Dual-red.svg)

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

---

## 🔒 Security & Cryptography (Military-Grade Protections)
This architecture is fortified with advanced cybersecurity protocols designed to defeat scrapers, brute-force bots, and unauthorized access attempts.

- **🕸️ The Honeypot (Tarpit) Architecture:** Instead of returning a standard `404 Not Found` for invalid links, the server intercepts unauthorized bots and returns a `200 OK` status while feeding them an infinite loop of generated garbage bytes. This actively exhausts the bot's bandwidth and RAM without consuming actual server storage.
- **🔄 Moving Target Defense (Dynamic Slug Rotator):** A background chron-job autonomously triggers every 6 to 24 hours to entirely wipe and regenerate new 32-character Hex URLs for all files in the database. This makes link-scraping mathematically impossible while safely preserving all internal subtitle and thumbnail linkages.
- **🛡️ WAF & Exponential Backoff (Fail2Ban Logic):** The API is protected by a self-healing IP rate-limiter. If an IP guesses incorrect links repeatedly, they are shadow-banned for 10 minutes, then 30 minutes, and so on. If a legitimate user makes a typo but subsequently enters a valid link, their penalty is instantly reset to zero.
- **⏳ Cryptographic Token Vault:** Original Hugging Face repository paths are permanently hidden. The system generates secure, time-bound access tokens (Basic, Pro, Ultra) with cryptographic signatures. These tokens have a "Rolling Expiry" (e.g., 4 hours) and strict anti-IDM (Internet Download Manager) headers to completely block piracy and direct downloading.

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

