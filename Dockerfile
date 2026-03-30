# Base image - 3.10 slim
FROM python:3.10-slim

# Hugging Face requirement: Non-root user
RUN useradd -m -u 1000 user

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# User switch karo aur Environment variables set karo
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Working directory
WORKDIR $HOME/app

# Requirements file pehle copy aur install karo (Caching ke liye)
COPY --chown=user requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Baaki code copy karo (main.py, bot.py, start.sh sab aayega isme)
COPY --chown=user . .

# start.sh ko executable banao taaki permission error na aaye
RUN chmod +x start.sh

# Hugging Face port
EXPOSE 7860

# CMD mein ab seedha start.sh run hoga
CMD ["./start.sh"]