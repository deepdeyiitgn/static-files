# 🚀 Qlynk Node Master (V1.4.1 Ultimate)

![Version](https://img.shields.io/badge/Version-1.4.1_Ultimate-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet.svg)
![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green.svg)
![License](https://img.shields.io/badge/License-Custom-red.svg)

**Qlynk Node Master** is an enterprise-grade, highly secure private cloud storage and streaming datacenter. Engineered to run entirely on Hugging Face Spaces (Free Tier), it acts as a self-sustaining media vault with an integrated Telegram ingestion bot, dynamic anti-hacker defenses, and a cinematic web player.

**Built by Deep Dey** (11th Grader & JEE Aspirant) 👨‍💻

---

## ✨ Enterprise Features
- **🤖 Omniscient Telegram Engine:** Upload directly via Telegram. Features an asynchronous queue system (`asyncio.Lock`) to prevent server crashes, automatic MKV to MP4 optimization via FFmpeg, and native thumbnail extraction.
- **🛡️ Secure Tokenized Streaming:** Original file URLs are never exposed. The system uses dynamic, time-limited tokens with a 4-hour "Rolling Expiry" to prevent piracy and direct downloads (IDM blocks).
- **🕸️ Anti-Hacker Tarpit (Honeypot):** Brute-force protection that feeds fake garbage bytes to unauthorized scrapers/bots while giving them a `200 OK` status, effectively wasting their time and bandwidth.
- **🎬 Cinematic Media Tube:** A beautiful, responsive web player with custom visualizers, auto-subtitle conversion (SRT to VTT), Playback Speed controls, Picture-in-Picture (PiP), and Spacebar shortcuts.
- **📊 God-Mode Telemetry:** Real-time WebSockets-powered dashboard (`/status`) showing core-by-core CPU usage, RAM pool, Network I/O, API latencies, and HF Cloud Quota.
- **♾️ 24/7 Self-Sustaining:** An automated anti-sleep background ping system keeps the HF container alive infinitely.

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

**⚠️ Copyright & Licensing Rules:**
You are free to fork, deploy, and use this architecture exactly as it is for your personal servers. However:
1. **No White-labeling:** You **CANNOT** remove, modify, or hide the attribution, developer credits (Deep Dey / Qlynk), or original copyright notices present in the code, UI, or Footer.
2. **Commercial Use:** Commercial distribution or selling this software as a SaaS product without explicit permission from the original author is strictly prohibited.

---

### 🌟 Support the Developer
If you found this architecture helpful or learned something new about API security and Python web servers, please give this repository a **⭐ Star**! 

*Dreaming of IIT Kharagpur CSE. Keep coding, keep building!*
```
