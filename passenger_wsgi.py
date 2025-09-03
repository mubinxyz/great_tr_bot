# passenger_wsgi.py 

import sys, os

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app from wsgi_bot.py
from wsgi_bot import app as application
