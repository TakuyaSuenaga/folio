import os
print("SET" if os.environ.get("HOME") else "NOTSET")
