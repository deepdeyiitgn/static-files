#!/bin/bash

# 1. Tere ping karne wale bot ko background mein start kar rahe hain
python bot.py &

# 2. Main FastAPI app ko Uvicorn ke through port 7860 pe start kar rahe hain
uvicorn main:app --host 0.0.0.0 --port 7860