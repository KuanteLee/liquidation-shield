import os
import time
from dotenv import load_dotenv
load_dotenv()

class Config:
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")

def main():
    print("Hello World")
    print(Config.API_KEY, Config.API_SECRET)
    time.sleep(10)

while True:
    main()