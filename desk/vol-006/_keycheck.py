import os
print("SET" if os.environ.get("GOOGLE_PLACES_API_KEY") else "NOTSET")
