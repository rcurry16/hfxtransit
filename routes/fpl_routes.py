from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import requests
import pandas as pd
from typing import Dict, List, Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Cache management
CACHE_DURATION = timedelta(minutes=15)
last_update: Dict[str, datetime] = {}
data_cache: Dict[str, any] = {}

async def fetch_fpl_data(data_type: str) -> dict:
    current_time = datetime.now()
    
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
        
        data_cache[data_type] = data
        last_update[data_type] = current_time
        
        return data
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"FPL API error: {str(e)}")

def process_player_data(data: dict) -> pd.DataFrame:
    df = pd.DataFrame(data['elements'])
    teams_df = pd.DataFrame(data['teams'])
    positions_df = pd.DataFrame(data['element_types'])
    
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

@router.get("/")
async def get_fpl_home(request: Request):
    return templates.TemplateResponse("fpl.html", {"request": request})

@router.get("/api/players")
async def get_players(min_minutes: Optional[int] = 0, position: Optional[str] = None):
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    if min_minutes > 0:
        df = df[df['minutes'] >= min_minutes]
    
    if position:
        df = df[df['singular_name_short'] == position.upper()]
    
    return df.to_dict(orient='records')

@router.get("/api/top-performers")
async def get_top_performers(position: Optional[str] = None, limit: int = 10):
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    if position:
        df = df[df['singular_name_short'] == position.upper()]
    
    return df.nlargest(limit, 'total_points').to_dict(orient='records')

@router.get("/api/value-picks")
async def get_value_picks(min_minutes: int = 90, limit: int = 10):
    data = await fetch_fpl_data("bootstrap")
    df = process_player_data(data)
    
    df = df[df['minutes'] >= min_minutes]
    df['value_score'] = df['total_points'] / df['now_cost']
    
    return df.nlargest(limit, 'value_score').to_dict(orient='records')

@router.get("/api/league-standings")
async def get_league_standings():
    data = await fetch_fpl_data("league")
    return data['standings']['results']

@router.get("/api/manager-history")
async def get_manager_history():
    # First get the league standings to get manager IDs
    league_data = await fetch_fpl_data("league")
    manager_ids = [manager['entry'] for manager in league_data['standings']['results']]
    
    # Fetch history for each manager
    all_histories = []
    for manager_id in manager_ids:
        try:
            response = requests.get(f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/")
            response.raise_for_status()
            history = response.json()
            
            # Process the current history
            current = history['current']
            for gw in current:
                all_histories.append({
                    'gameweek': gw['event'],
                    'points': gw['points'],
                    'total_points': gw['total_points'],
                    'manager_id': manager_id
                })
        except requests.RequestException as e:
            print(f"Error fetching history for manager {manager_id}: {e}")
            continue
    
    # Transform data for the chart
    df = pd.DataFrame(all_histories)
    pivot_df = df.pivot(index='gameweek', columns='manager_id', values='total_points').reset_index()
    
    return pivot_df.to_dict('records')
