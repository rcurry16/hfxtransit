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
  
