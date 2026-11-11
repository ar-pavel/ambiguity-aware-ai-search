"""Start the app: python3 app.py, then open http://127.0.0.1:8770 (--port N to change it).

The code lives in the assistant/ package; this file only starts its server.
"""
from assistant.server import main

if __name__ == "__main__":
    main()
