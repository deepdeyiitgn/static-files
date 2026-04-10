# 🛡️ Security Policy

## Supported Versions
Qlynk Node Master is currently on an active hiatus. Only the latest stable Enterprise release is monitored for critical security vulnerabilities.

| Version | Supported | Notes |
| ------- | ------------------ | ----- |
| V09.04.2026-stable (Enterprise) | ✅ | Latest Stable Release. |
| < V1.4.1 | ❌ | Deprecated. Please upgrade to the latest version. |

## 🏗️ Architecture & Active Defenses
This repository is engineered with military-grade security protocols. Before submitting a vulnerability report regarding bypasses or scrapers, please note that the system actively employs:
1. **Honeypot (Tarpit) Routing:** Invalid or unauthorized link guesses are intentionally met with a `200 OK` status and infinite garbage bytes to exhaust bot resources. This is intended behavior, not a vulnerability.
2. **Moving Target Defense:** 32-character file slugs rotate dynamically every 6-24 hours. Broken links due to rotation are a security feature, not a bug.
3. **WAF & IP Rate-Limiting:** Brute-force attempts will result in exponential shadow-bans (Fail2Ban logic). 
4. **Tokenized Vault:** Direct media downloads are blocked via rolling-expiry tokens and anti-IDM headers.

## 🚨 Reporting a Vulnerability
If you have discovered a legitimate security vulnerability that bypasses the active defenses mentioned above, please report it privately. **Do not open a public issue.**

**How to report:**
1. Send an email to: **[TERA_EMAIL_ID_YAHAN_DAAL@gmail.com]**
2. Include `[QLYNK SECURITY]` in the subject line.
3. Provide a detailed description of the vulnerability, the steps to reproduce it, and any potential impact.

**⚠️ Developer Notice (Hiatus):**
*The original author is currently in the 12th grade and on an active hiatus preparing for the JEE Advanced. Response times to security reports will be significantly delayed. Critical vulnerabilities will be patched as time permits, but immediate hotfixes cannot be guaranteed at this time.*

## 🚫 Out of Scope
The following are completely out of scope for this project and should not be reported:
* Vulnerabilities present in the underlying Hugging Face Spaces infrastructure (Report these to Hugging Face).
* Vulnerabilities present in the Telegram MTProto API.
* Social engineering or phishing attacks targeting the Space Password.
* Denial of Service (DoS) attacks that rely on overwhelming the Hugging Face free-tier limits.
