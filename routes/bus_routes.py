from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import requests
import folium
import json
from pathlib import Path
from utils.distance import haversine

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/bus")
async def get_bus_tracker(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/generate_map", response_class=HTMLResponse)
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

    for bus in feed.entity:
        if (search_type == "all" or 
            (search_type == "route" and route_num and bus.vehicle.trip.route_id == route_num) or
            (search_type == "bus" and bus_id and bus.id == bus_id)):
            
            latitude = bus.vehicle.position.latitude
            longitude = bus.vehicle.position.longitude
            label = bus.vehicle.vehicle.label

            folium.Marker(
                location=[latitude, longitude],
                popup=f"Bus ID: {label}\nRoute ID: {bus.vehicle.trip.route_id}",
                icon=folium.Icon(color="blue", icon="bus", prefix='fa')
            ).add_to(bus_map)

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

    # Save files with timestamp
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_directory = Path("static/locationdata")
    
    raw_data_filename = save_directory / f"{search_type}_buses_{current_time}.json"
    map_filename = save_directory / f"{search_type}_buses_{current_time}.html"

    with open(raw_data_filename, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    bus_map.save(str(map_filename))

    return templates.TemplateResponse("result.html", {
        "request": request,
        "map_url": f"/static/locationdata/{map_filename.name}",
        "json_url": f"/static/locationdata/{raw_data_filename.name}"
    })

@router.post("/filter_buses", response_class=HTMLResponse)
async def filter_buses(request: Request, lat: float = Form(...), lon: float = Form(...), radius: float = Form(...)):
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get('https://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb')
    feed.ParseFromString(response.content)

    map_center = [lat, lon]
    bus_map = folium.Map(location=map_center, zoom_start=12)
    json_data = []

    for bus in feed.entity:
        latitude = bus.vehicle.position.latitude
        longitude = bus.vehicle.position.longitude
        distance = haversine(lat, lon, latitude, longitude)

        if distance <= radius:
            label = bus.vehicle.vehicle.label
            folium.Marker(
                location=[latitude, longitude],
                popup=f"Bus ID: {label}\nDistance: {round(distance, 2)} km",
                icon=folium.Icon(color="blue", icon="bus", prefix='fa')
            ).add_to(bus_map)

            json_data.append({
                'bus_id': bus.id,
                'trip_id': bus.vehicle.trip.trip_id,
                'start_date': bus.vehicle.trip.start_date,
                'route_id': bus.vehicle.trip.route_id,
                'latitude': latitude,
                'longitude': longitude,
                'distance_from_user_km': round(distance, 2),
                'timestamp': bus.vehicle.timestamp,
                'speed': bus.vehicle.position.speed
            })

    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_directory = Path("static/locationdata")
    
    raw_data_filename = save_directory / f"buses_within_{radius}km_{current_time}.json"
    map_filename = save_directory / f"buses_within_{radius}km_{current_time}.html"

    with open(raw_data_filename, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    bus_map.save(str(map_filename))

    return templates.TemplateResponse("result.html", {
        "request": request,
        "map_url": f"/static/locationdata/{map_filename.name}",
        "json_url": f"/static/locationdata/{raw_data_filename.name}"
    })
  
