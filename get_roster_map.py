import requests
import json
import os

# --- CONFIGURATION ---
# !!! IMPORTANT: Replace 'YOUR_LEAGUE_ID' with your actual Sleeper League ID
LEAGUE_ID = '1189644119835193344' 
ROSTER_NAME_MAP_FILE = 'roster_name_map.json'

# --- API ENDPOINTS ---
BASE_URL = 'https://api.sleeper.app/v1/'

def fetch_and_create_roster_map(league_id: str):
    """
    Fetches league rosters and user data from the Sleeper API,
    then creates and saves a map from Roster ID to Team Name (Owner's Display Name).
    """
    if league_id == 'YOUR_LEAGUE_ID':
        print("ERROR: Please update LEAGUE_ID in the script with your actual Sleeper League ID.")
        return

    print(f"Fetching data for League ID: {league_id}...")

    # 1. Fetch Rosters
    rosters_url = f'{BASE_URL}league/{league_id}/rosters'
    rosters_response = requests.get(rosters_url)
    rosters_data = rosters_response.json()
    
    if not isinstance(rosters_data, list):
        print("ERROR: Failed to fetch rosters. Check if the League ID is correct.")
        return

    # 2. Fetch Users (Owners)
    users_url = f'{BASE_URL}league/{league_id}/users'
    users_response = requests.get(users_url)
    users_data = users_response.json()

    if not isinstance(users_data, list):
        print("ERROR: Failed to fetch user data.")
        return

    # 3. Create a User Map (user_id -> display_name)
    user_map = {}
    for user in users_data:
        user_id = user.get('user_id')
        display_name = user.get('display_name') or user.get('username', 'Unknown Team')
        if user_id:
            user_map[user_id] = display_name

    # 4. Create the Final Roster Map (roster_id -> team_name)
    roster_name_map = {}
    for roster in rosters_data:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        
        if roster_id and owner_id:
            team_name = user_map.get(owner_id, f'Owner {owner_id}')
            roster_name_map[roster_id] = team_name
            
    # 5. Save the map to a JSON file
    if roster_name_map:
        with open(ROSTER_NAME_MAP_FILE, 'w') as f:
            json.dump(roster_name_map, f, indent=4)
        print(f"\n✅ Successfully created {ROSTER_NAME_MAP_FILE} with {len(roster_name_map)} teams.")
    else:
        print("\nERROR: No rosters or users were successfully mapped.")

if __name__ == '__main__':
    fetch_and_create_roster_map(LEAGUE_ID)