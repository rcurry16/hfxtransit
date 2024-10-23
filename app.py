from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from routes import bus_routes
from routes import fpl_routes

# Initialize FastAPI app
app = FastAPI()

# Set up the static and template directories
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure required directories exist
Path("static/locationdata").mkdir(parents=True, exist_ok=True)

# Include routers
app.include_router(bus_routes.router)
app.include_router(fpl_routes.router, prefix="/fpl")

# Root route
@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})
    
