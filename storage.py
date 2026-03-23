
import os
from config import LOG_FILE, CSV_FILE

def append_log(msg):
    try:
        with open(LOG_FILE,"a") as f:
            f.write(msg + "\n")
    except:
        pass

def ensure_csv():
    try:
        if CSV_FILE not in os.listdir():
            with open(CSV_FILE,"w") as f:
                f.write("timestamp,temp,hum\n")
    except:
        pass

def append_csv(ts,t,h):
    try:
        with open(CSV_FILE,"a") as f:
            f.write("{},{},{}\n".format(ts,t,h))
    except:
        pass
