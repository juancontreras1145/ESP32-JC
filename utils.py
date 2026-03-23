
import time, os

def safe_str(x, n=16):
    try:
        return str(x)[:n]
    except:
        return "?"

def now_epoch():
    try:
        return time.time()
    except:
        return 0

def exists_file(name):
    try:
        return name in os.listdir()
    except:
        return False
