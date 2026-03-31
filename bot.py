import time
import random
import urllib.request
from datetime import datetime

URL = "https://deydeep-static-files.hf.space/"

print(f"Bot started! Will ping {URL} every 10-60 minutes.")

while True:
    # 10 se 60 minutes ko seconds mein convert kiya (600 to 3600 seconds)
    sleep_time = random.randint(600, 3600)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot sleeping for {sleep_time // 60} minutes...")
    time.sleep(sleep_time)
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Pinging {URL} to keep space alive...")
        # Request bhej rahe hain
        response = urllib.request.urlopen(URL)
        print(f"Ping successful! Status code: {response.getcode()}")
    except Exception as e:
        print(f"Ping failed: {e}")