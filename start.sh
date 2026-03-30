#!/bin/bash

# 1. Tere ping karne wale bot ko background mein start kar rahe hain
python bot.py &

# 2. Tera main app foreground mein chalega
python main.py