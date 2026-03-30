# Base image - 3.10 slim (halka aur fast)
FROM python:3.10-slim

# Hugging Face best practice: Create a non-root user
RUN useradd -m -u 1000 user

# System dependencies (sirf zaroori tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# User switch karo aur Environment variables set karo
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Working directory set karo
WORKDIR $HOME/app

# Requirements file copy karo aur install karo (Cache optimize karne ke liye chown lagana zaroori hai)
COPY --chown=user requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Baaki ka poora code copy karo
COPY --chown=user . .

# Hugging Face ka port open karo
EXPOSE 7860

# FastAPI / Uvicorn ko start karne ki command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]