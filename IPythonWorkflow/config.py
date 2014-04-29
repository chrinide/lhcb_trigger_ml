# Global constants,
# if you need to override them, do it in
# configlocal.py (create the file if it doesn't exist)
ipc_profile = None

try:
    from configlocal import *
except ImportError:
    print("No configlocal.py file was found, using default config")