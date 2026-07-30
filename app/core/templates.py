"""
app/core/templates.py

Single shared Jinja2Templates instance. Imported by main.py and by
any router that needs to render an HTML page, instead of each module
creating its own instance or importing from app.main (which would
cause circular imports).
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")