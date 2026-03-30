FROM python:3.10-slim

WORKDIR /app

# Removed unnecessary packages, added python-multipart
RUN pip install fastapi uvicorn huggingface_hub python-multipart jinja2

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]