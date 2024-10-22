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


@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
