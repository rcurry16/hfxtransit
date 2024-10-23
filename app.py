from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import requests
import folium
import json
from pathlib import Path
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Set up the static and template directories
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Update your routes
@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

# Rename your existing route to /bus
@app.get("/bus")
async def get_bus_tracker(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Placeholder route for the future soccer project
@app.get("/soccer")
async def get_soccer_project(request: Request):
    return templates.TemplateResponse("soccer.html", {"request": request})

@app.post("/generate_map", response_class=HTMLResponse)
async def generate_map(
    request: Request, 
    search_type: str = Form(...),
    route_num: str = Form(None),
    bus_id: str = Form(None)
):
    # Initialize the GTFS FeedMessage object
    feed = gtfs_realtime_pb2.FeedMessage()

    # Fetch the real-time bus position data
    response = requests.get('https://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb')
    feed.ParseFromString(response.content)

    # Create a map centered around Halifax
    map_center = [44.6488, -63.5752]  # Coordinates for Halifax
    bus_map = folium.Map(location=map_center, zoom_start=12)

    # Prepare data for JSON output
    json_data = []

    # Handle different search types
    if search_type == "all":
        # Iterate over all buses and add them to the map
        for bus in feed.entity:
            latitude = bus.vehicle.position.latitude
            longitude = bus.vehicle.position.longitude
            label = bus.vehicle.vehicle.label

            folium.Marker(
                location=[latitude, longitude],
                popup=f"Bus ID: {label}\nRoute ID: {bus.vehicle.trip.route_id}",
                icon=folium.Icon(color="blue", icon="bus", prefix='fa')
            ).add_to(bus_map)

            # Add the bus data to JSON output
            bus_data = {
                'bus_id': bus.id,
                'trip_id': bus.vehicle.trip.trip_id,
                'route_id': bus.vehicle.trip.route_id,
                'latitude': latitude,
                'longitude': longitude,
                'timestamp': bus.vehicle.timestamp,
                'speed': bus.vehicle.position.speed
            }
            json_data.append(bus_data)

    elif search_type == "route" and route_num:
        # Search by route number
        for bus in feed.entity:
            if bus.vehicle.trip.route_id == route_num:
                latitude = bus.vehicle.position.latitude
                longitude = bus.vehicle.position.longitude
                label = bus.vehicle.vehicle.label

                folium.Marker(
                    location=[latitude, longitude],
                    popup=f"Bus ID: {label}\nRoute ID: {route_num}",
                    icon=folium.Icon(color="blue", icon="bus", prefix='fa')
                ).add_to(bus_map)

                # Add the bus data to JSON output
                bus_data = {
                    'bus_id': bus.id,
                    'trip_id': bus.vehicle.trip.trip_id,
                    'route_id': route_num,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': bus.vehicle.timestamp,
                    'speed': bus.vehicle.position.speed
                }
                json_data.append(bus_data)

    elif search_type == "bus" and bus_id:
        # Search by bus ID
        for bus in feed.entity:
            if bus.id == bus_id:
                latitude = bus.vehicle.position.latitude
                longitude = bus.vehicle.position.longitude
                label = bus.vehicle.vehicle.label

                folium.Marker(
                    location=[latitude, longitude],
                    popup=f"Bus ID: {bus_id}",
                    icon=folium.Icon(color="blue", icon="bus", prefix='fa')
                ).add_to(bus_map)

                # Add the bus data to JSON output
                bus_data = {
                    'bus_id': bus.id,
                    'trip_id': bus.vehicle.trip.trip_id,
                    'route_id': bus.vehicle.trip.route_id,
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp': bus.vehicle.timestamp,
                    'speed': bus.vehicle.position.speed
                }
                json_data.append(bus_data)

    # Get the current date and time for file names
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define paths to save the map and JSON
    save_directory = Path("static/locationdata")
    save_directory.mkdir(parents=True, exist_ok=True)
    
    raw_data_filename = save_directory / f"{search_type}_buses_{current_time}.json"
    map_filename = save_directory / f"{search_type}_buses_{current_time}.html"

    # Save the raw data as JSON
    with open(raw_data_filename, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    # Save the generated map
    bus_map.save(str(map_filename))

    # Return the result HTML with links to the generated files
    return templates.TemplateResponse("result.html", {
        "request": request,
        "map_url": f"/static/locationdata/{map_filename.name}",
        "json_url": f"/static/locationdata/{raw_data_filename.name}"
    })

import math

def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers
    R = 6371.0

    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Differences in latitudes and longitudes
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Distance in kilometers
    distance = R * c

    return distance

@app.post("/filter_buses", response_class=HTMLResponse)
async def filter_buses(request: Request, lat: float = Form(...), lon: float = Form(...), radius: float = Form(...)):
    # Initialize the GTFS FeedMessage object
    feed = gtfs_realtime_pb2.FeedMessage()

    # Fetch the real-time bus position data
    response = requests.get('https://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb')
    feed.ParseFromString(response.content)

    # Create a map centered around the user's location
    map_center = [lat, lon]
    bus_map = folium.Map(location=map_center, zoom_start=12)

    # Prepare data for JSON output
    json_data = []

    # Iterate over each bus entity in the feed
    for bus in feed.entity:
        latitude = bus.vehicle.position.latitude
        longitude = bus.vehicle.position.longitude
        label = bus.vehicle.vehicle.label

        # Calculate the distance between the user-provided lat/lon and the bus location
        distance = haversine(lat, lon, latitude, longitude)

        # Check if the bus is within the specified radius
        if distance <= radius:
            # Add marker for the bus position on the map
            folium.Marker(
                location=[latitude, longitude],
                popup=f"Bus ID: {label}\nDistance: {round(distance, 2)} km",
                icon=folium.Icon(color="blue", icon="bus", prefix='fa')
            ).add_to(bus_map)

            # Prepare JSON data
            bus_data = {
                'bus_id': bus.id,
                'trip_id': bus.vehicle.trip.trip_id,
                'start_date': bus.vehicle.trip.start_date,
                'route_id': bus.vehicle.trip.route_id,
                'latitude': latitude,
                'longitude': longitude,
                'distance_from_user_km': round(distance, 2),
                'timestamp': bus.vehicle.timestamp,
                'speed': bus.vehicle.position.speed
            }
            json_data.append(bus_data)

    # Get the current date and time for file names
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define paths to save the map and JSON
    save_directory = Path("static/locationdata")
    save_directory.mkdir(parents=True, exist_ok=True)
    
    raw_data_filename = save_directory / f"buses_within_{radius}km_{current_time}.json"
    map_filename = save_directory / f"buses_within_{radius}km_{current_time}.html"

    # Save the raw data as JSON
    with open(raw_data_filename, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    # Save the generated map
    bus_map.save(str(map_filename))

    # Return the result HTML with links to the generated files
    return templates.TemplateResponse("result.html", {
        "request": request,
        "map_url": f"/static/locationdata/{map_filename.name}",
        "json_url": f"/static/locationdata/{raw_data_filename.name}"
    })

# In your main app.py, add:
@app.mount("/fpl", fpl_app)  # Mount the FPL app as a sub-application

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, List, Optional

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Cache management
CACHE_DURATION = timedelta(minutes=15)
last_update: Dict[str, datetime] = {}
data_cache: Dict[str, any] = {}

async def fetch_fpl_data(data_type: str) -> dict:
    """Fetch data from FPL API with caching"""
    current_time = datetime.now()
    
    # Return cached data if it's still valid
    if (data_type in last_update and 
        data_type in data_cache and 
        current_time - last_update[data_type] < CACHE_DURATION):
        return data_cache[data_type]
    
    base_url = "https://fantasy.premierleague.com/api"
    endpoints = {
        "bootstrap": f"{base_url}/bootstrap-static/",
        "league": f"{base_url}/leagues-classic/247541/standings/"
    }
    
    try:
        response = requests.get(endpoints[data_type])
        response.raise_for_status()
        data = response.json()
        
        # Update cache
        data_cache[data_type] = data
        last_update[data_type] = current_time
        
        return data
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"FPL API error: {str(e)}")

def process_player_data(data: dict) -> pd.DataFrame:
    """Process and clean player data"""
    df = pd.DataFrame(data['elements'])
    teams_df = pd.DataFrame(data['teams'])
    positions_df = pd.DataFrame(data['element_types'])
    
    # Basic player info
    selected_columns = [
        'id', 'web_name', 'team', 'element_type', 'now_cost', 
        'total_points', 'minutes', 'goals_scored', 'assists', 
        'clean_sheets', 'form'
    ]
    
    players_df = df[selected_columns].merge(
        teams_df[['id', 'name', 'short_name']], 
        left_on='team', 
        right_on='id', 
        suffixes=('_player', '_team')
    ).merge(
        positions_df[['id', 'singular_name_short']], 
        left_on='element_type', 
        right_on='id', 
        suffixes=('', '_position')
    )
    
    return players_df

@app.get("/")
async def get_fpl_home(request: Request):
    return templates.TemplateResponse("fpl.html", {
        "request": request
    })

@app.get("/api/players")
async def get_players(min_minutes: Optional[int] = 0, position: Optional[str] = None):
    """Get player data with optional filters"""
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    if min_minutes > 0:
        df = df[df['minutes'] >= min_minutes]
    
    if position:
        df = df[df['singular_name_short'] == position.upper()]
    
    return df.to_dict(orient='records')

@app.get("/api/top-performers")
async def get_top_performers(position: Optional[str] = None, limit: int = 10):
    """Get top performing players"""
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    if position:
        df = df[df['singular_name_short'] == position.upper()]
    
    return df.nlargest(limit, 'total_points').to_dict(orient='records')

@app.get("/api/value-picks")
async def get_value_picks(min_minutes: int = 90, limit: int = 10):
    """Get best value players (points per cost)"""
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    df = df[df['minutes'] >= min_minutes]
    df['value_score'] = df['total_points'] / df['now_cost']
    
    return df.nlargest(limit, 'value_score').to_dict(orient='records')
