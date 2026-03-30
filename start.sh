#!/bin/bash

# 1. Bot ko background mein start karo
python bot.py &

# 2. Main FastAPI app ko foreground mein start karo
uvicorn main:app --host 0.0.0.0 --port 7860