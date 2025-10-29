import pandas as pd
import json
import os

# --- FILE CONFIGURATION ---
PLAYER_DATA_FILE = 'sleeper_players.json'
ROSTER_NAME_MAP_FILE = 'roster_name_map.json'
DATA_FOLDER = 'ytd_matchups_data'
OUTPUT_CSV_FILE = 'optimal_lineup_analysis.csv'

# --- STARTER SLOT DEFINITION ---
STARTER_SLOTS = {
    'QB': 1,
    'RB': 2,
    'WR': 3,
    'TE': 1,
    'FLEX': 2,
    'SUPERFLEX': 1
}

# --- MAP LOADING FUNCTIONS ---

def load_maps():
    """Loads player data and roster data to create necessary maps."""
    
    # 1. Load Player Data (Name and Position)
    print(f"Loading player data from {PLAYER_DATA_FILE}...")
    try:
        with open(PLAYER_DATA_FILE, 'r') as f:
            player_data = json.load(f)
    except Exception as e:
        print(f"FATAL ERROR loading {PLAYER_DATA_FILE}: {e}")
        return None, None, None
        
    position_map = {p_id: details.get('position') for p_id, details in player_data.items() if details.get('position')}
    name_map = {p_id: details.get('full_name') for p_id, details in player_data.items() if details.get('full_name')}
    
    # 2. Load Roster Map (ID to Team Name)
    print(f"Loading roster map from {ROSTER_NAME_MAP_FILE}...")
    try:
        with open(ROSTER_NAME_MAP_FILE, 'r') as f:
            roster_map = {str(k): v for k, v in json.load(f).items()}
    except Exception as e:
        print(f"FATAL ERROR loading {ROSTER_NAME_MAP_FILE}: {e}")
        return None, None, None
        
    # Standardize DEF for mapping
    position_map = {k: v.replace('DEF', 'D/ST') for k, v in position_map.items()}
    
    return position_map, name_map, roster_map


# --- DATA PROCESSING FUNCTION (FIXED: Filtered out 0.0 scores) ---

def process_matchup_data(position_map, name_map, roster_map, data_folder=DATA_FOLDER):
    """
    Processes all weekly matchup data to find every player's score and determine 
    their current team, while filtering out 0.0 scores (likely due to bye/inactivity).
    """
    print(f"\nProcessing matchup data from {data_folder}...")
    all_player_scores = []
    player_to_roster = {} 
    
    ELIGIBLE_POSITIONS = ['QB', 'RB', 'WR', 'TE']
    # Define a minimum threshold for a "playing" week score
    MIN_PLAYING_SCORE = 0.1 

    if not os.path.exists(data_folder):
        print(f"FATAL ERROR: Matchup data folder '{data_folder}' was not found.")
        return None

    for filename in os.listdir(data_folder):
        if filename.startswith("matchups_week_") and filename.endswith(".json"):
            file_path = os.path.join(data_folder, filename)
            
            with open(file_path, 'r') as f:
                week_data = json.load(f)
            
            if not isinstance(week_data, list): continue

            for box_score in week_data:
                roster_id = str(box_score.get('roster_id'))
                players = box_score.get('players', [])
                player_points_map = box_score.get('players_points', {}) 

                if not players or not player_points_map: continue

                for player_id in players:
                    points = player_points_map.get(player_id)
                    position = position_map.get(player_id, 'UNK')
                    
                    if points is not None and position in ELIGIBLE_POSITIONS:
                        # --- KEY CHANGE: Only record scores >= MIN_PLAYING_SCORE ---
                        if points >= MIN_PLAYING_SCORE:
                            all_player_scores.append([player_id, points])
                        
                        # Update ownership to the latest roster seen regardless of score
                        player_to_roster[player_id] = roster_id

    if not all_player_scores:
        print("ERROR: No non-zero player scores successfully loaded. Check data consistency.")
        return None

    df_scores = pd.DataFrame(all_player_scores, columns=['Player_ID', 'Points'])
    
    # Calculate median points for each player
    df_median = df_scores.groupby('Player_ID')['Points'].median().reset_index()
    df_median.rename(columns={'Points': 'Median_Points'}, inplace=True)
    
    # Merge with maps
    df_median['Position'] = df_median['Player_ID'].map(position_map)
    df_median['Player_Name'] = df_median['Player_ID'].map(name_map)
    df_median['Roster_ID'] = df_median['Player_ID'].map(player_to_roster)
    
    # Filter for valid players and sort by median score
    df_median = df_median.dropna(subset=['Position', 'Roster_ID'])
    df_median = df_median[df_median['Position'].isin(ELIGIBLE_POSITIONS)]
    df_median.sort_values(by=['Roster_ID', 'Median_Points'], ascending=[True, False], inplace=True)
    
    return df_median


# --- OPTIMAL LINEUP SELECTION (No changes here) ---

def select_optimal_lineup(df_median):
    """Selects the highest median-scoring player for each starting slot for every team."""
    
    optimal_lineup_data = []
    
    MANDATORY_SLOTS = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1}
    FLEX_ELIGIBLE = ['RB', 'WR', 'TE']
    SF_ELIGIBLE = ['QB', 'RB', 'WR', 'TE']

    for roster_id, team_df in df_median.groupby('Roster_ID'):
        
        selected_players = []
        selected_ids = set()
        
        available_pool = team_df.copy()
        
        # 1. Select Mandatory Positions (QB, RB, WR, TE)
        for pos, count in MANDATORY_SLOTS.items():
            pos_players = available_pool[available_pool['Position'] == pos].head(count)
            
            for index, player in pos_players.iterrows():
                selected_players.append({
                    'Roster_ID': roster_id,
                    'Position': pos,
                    'Player_Name': player['Player_Name'],
                    'Median_Points': player['Median_Points']
                })
                selected_ids.add(player['Player_ID'])

        # Update the available pool by removing mandatory selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]

        # 2. Select FLEX (2 spots: RB/WR/TE)
        # Select the best remaining players from the FLEX pool
        flex_pool = available_pool[available_pool['Position'].isin(FLEX_ELIGIBLE)].head(STARTER_SLOTS['FLEX'])
        
        for index, player in flex_pool.iterrows():
            selected_players.append({
                'Roster_ID': roster_id,
                'Position': 'FLEX',
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points']
            })
            selected_ids.add(player['Player_ID'])

        # Update the available pool by removing FLEX selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]
        
        # 3. Select SUPERFLEX (1 spot: best remaining QB/RB/WR/TE)
        # Select the single best remaining player from the combined pool
        sf_pool = available_pool[available_pool['Position'].isin(SF_ELIGIBLE)].head(STARTER_SLOTS['SUPERFLEX'])

        for index, player in sf_pool.iterrows():
            selected_players.append({
                'Roster_ID': roster_id,
                'Position': 'SUPERFLEX',
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points']
            })

        optimal_lineup_data.extend(selected_players)

    return pd.DataFrame(optimal_lineup_data)


# --- OUTPUT FORMATTING (No functional changes here) ---

def format_output_csv(df_optimal, roster_map):
    """Formats the DataFrame with summary rows and outputs to CSV."""
    
    final_output = []
    
    category_order = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX']
    
    sorted_roster_ids = sorted(df_optimal['Roster_ID'].unique(), key=int)
    
    for roster_id in sorted_roster_ids:
        team_df = df_optimal[df_optimal['Roster_ID'] == roster_id].copy()
        team_name = roster_map.get(roster_id, f"Roster {roster_id}")
        
        team_df['Team Name'] = team_name
        
        detail_rows = team_df[['Team Name', 'Position', 'Player_Name', 'Median_Points']].copy()
        detail_rows.rename(columns={'Player_Name': 'Player Name', 'Median_Points': 'Median Points'}, inplace=True)
        
        detail_rows['Position_Category'] = pd.Categorical(
            detail_rows['Position'], 
            categories=category_order, 
            ordered=True
        )

        # 2. Assign a slot index for secondary sorting (FIXED WARNING: added observed=True)
        detail_rows = detail_rows.sort_values(by=['Position_Category', 'Median Points'], ascending=[True, False])
        detail_rows['Slot_Index'] = detail_rows.groupby('Position_Category', observed=True).cumcount()

        # 3. Sort by Category (QB before RB) then by Index (RB1 before RB2)
        detail_rows = detail_rows.sort_values(
            by=['Position_Category', 'Slot_Index']
        ).drop(columns=['Position_Category', 'Slot_Index'])
        
        final_output.append(detail_rows)
        
        total_median = team_df['Median_Points'].sum()
        summary_row = pd.DataFrame([{
            'Team Name': team_name,
            'Position': 'TOTAL',
            'Player Name': '',
            'Median Points': total_median
        }])
        
        final_output.append(summary_row)

    df_final_output = pd.concat(final_output, ignore_index=True)
    
    # Output to CSV
    df_final_output.to_csv(OUTPUT_CSV_FILE, index=False)
    
    print(f"\n✅ Success! Optimal lineups saved to {OUTPUT_CSV_FILE}")
    print("The CSV includes columns: Team Name, Position, Player Name, Median Points, with a 'TOTAL' row for each team.")
    
    try:
        # Use float format to clean up the decimal presentation in the console
        return df_final_output.head(20).to_markdown(index=False, floatfmt=".2f")
    except ImportError:
        print("\nNOTE: Could not display table preview in terminal. Please install 'tabulate' for previews: pip install tabulate")
        return None 


# --- MAIN EXECUTION ---

if __name__ == '__main__':
    position_map, name_map, roster_map = load_maps()
    
    if position_map is None or name_map is None or roster_map is None:
        print("\nScript failed due to missing files or data loading errors.")
    else:
        df_median_scores = process_matchup_data(position_map, name_map, roster_map)
        
        if df_median_scores is not None and not df_median_scores.empty:
            df_optimal_lineup = select_optimal_lineup(df_median_scores)
            
            if not df_optimal_lineup.empty:
                preview = format_output_csv(df_optimal_lineup, roster_map)
                if preview:
                    print("\n--- PREVIEW OF OPTIMAL LINEUP CSV (Filtered Byes) ---")
                    print(preview)
            else:
                print("\nError: Could not determine any optimal lineups.")
        else:
            print("\nError: Failed to calculate median scores.")