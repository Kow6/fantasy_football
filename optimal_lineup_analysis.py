import pandas as pd
import json
import os
import numpy as np

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
FLEX_ELIGIBLE = ['RB', 'WR', 'TE']
SF_ELIGIBLE = ['QB', 'RB', 'WR', 'TE']

# Define a minimum threshold for a "playing" week score (used for bye/inactivity filtering)
MIN_PLAYING_SCORE = 0.1 

# --- MAP LOADING FUNCTIONS ---

def load_maps():
    """
    Loads player data and roster data. Creates position_map (all scoring-eligible players) 
    and full_position_map (all players). IR players are tracked in ir_players for later filtering, 
    but are NOT removed from position_map if they are an eligible position.
    """
    
    print(f"Loading player data from {PLAYER_DATA_FILE}...")
    try:
        with open(PLAYER_DATA_FILE, 'r') as f:
            player_data = json.load(f)
    except Exception as e:
        print(f"FATAL ERROR loading {PLAYER_DATA_FILE}: {e}")
        return None, None, None, None, None
        
    position_map = {} # ALL eligible position players (used for median calculation)
    full_position_map = {} # All players (used for ownership tracking)
    name_map = {}
    ir_players = {} # Only used to flag players as IR
    
    for p_id, details in player_data.items():
        position = details.get('position')
        full_name = details.get('full_name')
        injury_status = details.get('injury_status')
        
        if position and full_name:
            standard_position = position.replace('DEF', 'D/ST')

            # 1. Populate the map used for ownership tracking (all players)
            full_position_map[p_id] = standard_position
            name_map[p_id] = full_name
            
            # 2. Flag IR players. They are NOT removed from position_map.
            if injury_status == "IR":
                ir_players[p_id] = {'Player_Name': full_name, 'Position': standard_position}
            
            # 3. Populate the map used for median calculation (includes IR players who have a score history)
            position_map[p_id] = standard_position
    
    print(f"Loaded player data for {len(position_map)} total players (including IR).")

    # 4. Load Roster Map (ID to Team Name)
    print(f"Loading roster map from {ROSTER_NAME_MAP_FILE}...")
    try:
        with open(ROSTER_NAME_MAP_FILE, 'r') as f:
            roster_map = {str(k): v for k, v in json.load(f).items()}
    except Exception as e:
        print(f"FATAL ERROR loading {ROSTER_NAME_MAP_FILE}: {e}")
        return None, None, None, None, None
        
    return position_map, name_map, roster_map, ir_players, full_position_map


# --- DATA PROCESSING FUNCTION (NO LOGIC CHANGE NEEDED HERE NOW) ---

def process_matchup_data(position_map, name_map, roster_map, full_position_map, data_folder=DATA_FOLDER):
    """
    Processes all weekly matchup data, tracks scores, handles trade logic, and applies filters.
    """
    print(f"\nProcessing matchup data from {data_folder}...")
    all_player_scores = []
    player_scores_by_week = {} 
    
    player_ownership_history = {} 
    
    ELIGIBLE_POSITIONS = ['QB', 'RB', 'WR', 'TE']
    max_week_num = 0 

    if not os.path.exists(data_folder):
        print(f"FATAL ERROR: Matchup data folder '{data_folder}' was not found.")
        return None, None, {}

    # Step 1: Accumulate scores and track latest ownership
    for filename in os.listdir(data_folder):
        if filename.startswith("matchups_week_") and filename.endswith(".json"):
            file_path = os.path.join(data_folder, filename)
            
            try:
                with open(file_path, 'r') as f:
                    week_data = json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                continue
            
            if not isinstance(week_data, list): continue

            try:
                week_num = int(filename.split('_')[2].split('.')[0])
                if week_num > max_week_num:
                    max_week_num = week_num
            except:
                week_num = 0

            for box_score in week_data:
                roster_id = str(box_score.get('roster_id'))
                players = box_score.get('players', [])
                player_points_map = box_score.get('players_points', {}) 

                if not players: continue

                for player_id in players:
                    position = full_position_map.get(player_id) 
                    
                    if position in ELIGIBLE_POSITIONS:
                        points = player_points_map.get(player_id)
                        
                        # Record scores for ALL players in eligible positions
                        
                        # Store ALL scores for the last 2 week check
                        if player_id not in player_scores_by_week:
                            player_scores_by_week[player_id] = []
                        if points is not None:
                            player_scores_by_week[player_id].append({'week': week_num, 'points': points})
                        
                        # Only record non-zero scores for median calculation
                        if points is not None and points >= MIN_PLAYING_SCORE:
                            all_player_scores.append([player_id, points])
                        
                        # --- TRADE LOGIC: Update ownership for ALL eligible positions ---
                        if player_id not in player_ownership_history or week_num >= player_ownership_history[player_id]['week']:
                            player_ownership_history[player_id] = {'roster_id': roster_id, 'week': week_num}
                            
    if not player_ownership_history:
        print("ERROR: No player scores or ownership history successfully loaded. Check data consistency.")
        return None, None, {} 

    player_to_roster = {p_id: data['roster_id'] for p_id, data in player_ownership_history.items()}

    # Step 2: Calculate stats and apply Disqualification Filters
    
    if not all_player_scores:
        print("Warning: No non-zero scores found. Cannot calculate median scores.")
        return pd.DataFrame(), pd.DataFrame(), player_to_roster

    df_scores = pd.DataFrame(all_player_scores, columns=['Player_ID', 'Points'])
    
    df_stats = df_scores.groupby('Player_ID')['Points'].agg(['median', 'count']).reset_index()
    df_stats.rename(columns={'median': 'Median_Points', 'count': 'Score_Count'}, inplace=True)
    
    # --- EXCLUSION CHECK 2 & 3: Zeros and Single Matchup ---
    players_to_exclude_zeros = set()
    latest_week = max_week_num
    
    for player_id, scores in player_scores_by_week.items():
        sorted_scores = sorted([s for s in scores if s['week'] >= latest_week - 1], key=lambda x: x['week'], reverse=True)
        if len(sorted_scores) >= 2:
            last_score = sorted_scores[0]['points']
            second_last_score = sorted_scores[1]['points']
            if last_score < MIN_PLAYING_SCORE and second_last_score < MIN_PLAYING_SCORE:
                players_to_exclude_zeros.add(player_id)

    players_to_exclude_single_matchup = set()
    if max_week_num >= 4:
        single_matchup_players = df_stats[df_stats['Score_Count'] == 1]['Player_ID'].tolist()
        players_to_exclude_single_matchup.update(single_matchup_players)
        
    players_to_exclude_all = players_to_exclude_zeros.union(players_to_exclude_single_matchup)
    
    excluded_single_matchup_data = df_stats[df_stats['Player_ID'].isin(players_to_exclude_single_matchup)].copy()
    
    # Filter out all excluded players for the final median calculation
    # NOTE: IR players who are NOT filtered by zeros/SMF REMAIN in df_median
    df_median = df_stats[~df_stats['Player_ID'].isin(players_to_exclude_all)].copy()
    df_median.drop(columns=['Score_Count'], inplace=True) 
    
    # Merge with maps
    df_median['Position'] = df_median['Player_ID'].map(position_map) 
    df_median['Player_Name'] = df_median['Player_ID'].map(name_map)
    df_median['Roster_ID'] = df_median['Player_ID'].map(player_to_roster)
    
    # Final cleanup and sort
    df_median = df_median.dropna(subset=['Position', 'Roster_ID'])
    df_median = df_median[df_median['Position'].isin(ELIGIBLE_POSITIONS)]
    df_median.sort_values(by=['Roster_ID', 'Median_Points'], ascending=[True, False], inplace=True)
    
    # Prepare excluded single-matchup players list for output
    excluded_single_matchup_list = []
    for index, row in excluded_single_matchup_data.iterrows():
        p_id = row['Player_ID']
        roster_id = player_to_roster.get(p_id)
        position = full_position_map.get(p_id)
        if roster_id and position:
            excluded_single_matchup_list.append({
                'Player_ID': p_id,
                'Roster_ID': roster_id,
                'Position': position,
                'Player_Name': name_map.get(p_id),
                'Median_Points': row['Median_Points'],
                'Reason': 'Single Matchup Filter'
            })
        
    df_excluded_single_matchup = pd.DataFrame(excluded_single_matchup_list).dropna(subset=['Roster_ID', 'Position'])

    return df_median, df_excluded_single_matchup, player_to_roster


# --- OPTIMAL LINEUP SELECTION (NO CHANGES) ---

def select_optimal_lineup(df_median):
    """
    Selects the optimal lineup and returns all remaining non-starter players for backup analysis.
    The starting lineup is 10 slots: QB, 2RB, 3WR, 1TE, 2FLEX, 1SUPERFLEX.
    """
    
    optimal_lineup_data = []
    remaining_players = []
    
    MANDATORY_SLOTS = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1}

    for roster_id, team_df in df_median.groupby('Roster_ID'):
        
        selected_ids = set()
        available_pool = team_df.copy()
        
        # 1. Select Mandatory Positions (QB, RB, WR, TE)
        for pos, count in MANDATORY_SLOTS.items():
            pos_players = available_pool[available_pool['Position'] == pos].head(count)
            
            for index, player in pos_players.iterrows():
                optimal_lineup_data.append({
                    'Roster_ID': roster_id,
                    'Position_Slotted': pos, 
                    'Inherent_Position': player['Position'], 
                    'Player_Name': player['Player_Name'],
                    'Median_Points': player['Median_Points'],
                    'Player_ID': player['Player_ID'] 
                })
                selected_ids.add(player['Player_ID'])

        # Update the available pool by removing mandatory selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]

        # 2. Select FLEX (2 spots: RB/WR/TE)
        flex_pool = available_pool[available_pool['Position'].isin(FLEX_ELIGIBLE)].head(STARTER_SLOTS['FLEX'])
        
        for index, player in flex_pool.iterrows():
            optimal_lineup_data.append({
                'Roster_ID': roster_id,
                'Position_Slotted': 'FLEX', 
                'Inherent_Position': player['Position'],
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points'],
                'Player_ID': player['Player_ID']
            })
            selected_ids.add(player['Player_ID'])

        # Update the available pool by removing FLEX selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]
        
        # 3. Select SUPERFLEX (1 spot: best remaining QB/RB/WR/TE)
        sf_pool = available_pool[available_pool['Position'].isin(SF_ELIGIBLE)].head(STARTER_SLOTS['SUPERFLEX'])

        for index, player in sf_pool.iterrows():
            optimal_lineup_data.append({
                'Roster_ID': roster_id,
                'Position_Slotted': 'SUPERFLEX', 
                'Inherent_Position': player['Position'],
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points'],
                'Player_ID': player['Player_ID']
            })
            selected_ids.add(player['Player_ID'])

        # 4. Collect Remaining Players (for backup analysis)
        remaining_df = available_pool[~available_pool['Player_ID'].isin(selected_ids)].copy()
        
        for index, player in remaining_df.iterrows():
             remaining_players.append({
                'Roster_ID': roster_id,
                'Position': player['Position'], 
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points'],
                'Player_ID': player['Player_ID']
            })

    df_optimal = pd.DataFrame(optimal_lineup_data).rename(columns={'Position_Slotted': 'Position'})
    return df_optimal, pd.DataFrame(remaining_players)


# --- OUTPUT FORMATTING (WITH IR TRUE SCORE LOOKUP) ---

def format_output_csv(df_optimal, df_remaining, roster_map, ir_players_dict, df_excluded_single_matchup, player_to_roster, df_median_scores):
    """
    Formats the DataFrame with optimal lineup, total score, top backups, and disqualified players, 
    using the true median score for IR players who have played.
    """
    
    FINAL_COLUMNS = ['Team Name', 'Position', 'Player Name', 'Median Points']
    
    # --- STEP 1: Add Team Name to DataFrames ---
    roster_name_df = pd.DataFrame(roster_map.items(), columns=['Roster_ID', 'Team Name'])
    
    if not df_optimal.empty:
        df_optimal = pd.merge(df_optimal, roster_name_df, on='Roster_ID', how='left')
    
    if not df_remaining.empty:
        df_remaining = pd.merge(df_remaining, roster_name_df, on='Roster_ID', how='left')

    # Calculate totals and sort teams by TOTAL score 
    df_totals = df_optimal.groupby('Roster_ID')['Median_Points'].sum().reset_index()
    df_totals.rename(columns={'Median_Points': 'Total_Median_Points'}, inplace=True)
    df_totals.sort_values(by='Total_Median_Points', ascending=False, inplace=True)
    sorted_roster_ids = df_totals['Roster_ID'].tolist()
    
    # --- Prepare Disqualified Lists & Maps ---
    category_order = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX']
    backup_positions = ['QB', 'RB', 'WR', 'TE']

    # 1a. Build IR Disqualified List (Lookup true score if it exists)
    ir_players_list = []
    # Create a mapping of Player_ID -> Median_Points for quick lookup
    score_lookup = df_median_scores.set_index('Player_ID')['Median_Points'].to_dict()
    
    for p_id, data in ir_players_dict.items():
        roster_id = player_to_roster.get(p_id) 
        if roster_id:
            # Get the true median score. If not found, player never recorded a non-zero score.
            median_score = score_lookup.get(p_id, 0.0) 
            
            ir_players_list.append({
                'Roster_ID': roster_id,
                'Position': data['Position'],
                'Player Name': data['Player_Name'],
                'Median Points': median_score, # Use the true median (or 0.0) for competitiveness check
                'Reason': 'IR Status'
            })
            
    df_excluded_ir = pd.DataFrame(
        ir_players_list, 
        columns=['Roster_ID', 'Position', 'Player Name', 'Median Points', 'Reason']
    )

    # 1b. Prepare Single Matchup list
    if not df_excluded_single_matchup.empty:
        df_excluded_single_matchup.rename(columns={'Player_Name': 'Player Name', 'Median_Points': 'Median Points'}, inplace=True)
        df_excluded_single_matchup['Reason'] = 'Single Matchup Filter'

    # 2. Calculate Cutoffs (No Change)
    relevant_player_scores_by_team = {} 
    positional_cutoffs_by_team = {}    

    for roster_id in sorted_roster_ids:
        team_optimal = df_optimal[df_optimal['Roster_ID'] == roster_id].copy()
        team_remaining = df_remaining[df_remaining['Roster_ID'] == roster_id].copy()

        relevant_player_data_for_cutoff = team_optimal[['Inherent_Position', 'Median_Points']].copy()
        
        for pos in backup_positions: 
            top_backup = team_remaining[team_remaining['Position'] == pos].head(1)
            if not top_backup.empty:
                new_index = len(relevant_player_data_for_cutoff)
                relevant_player_data_for_cutoff.loc[new_index] = [top_backup.iloc[0]['Position'], top_backup.iloc[0]['Median_Points']] 
        
        all_relevant_scores = relevant_player_data_for_cutoff['Median_Points'].tolist()
        overall_cutoff = min(all_relevant_scores) if all_relevant_scores else -1.0
        relevant_player_scores_by_team[roster_id] = overall_cutoff

        positional_cutoffs = {}
        for pos in backup_positions:
            pos_scores = relevant_player_data_for_cutoff[relevant_player_data_for_cutoff['Inherent_Position'] == pos]['Median_Points'].tolist()
            if pos_scores:
                positional_cutoffs[pos] = min(pos_scores)
            
        positional_cutoffs_by_team[roster_id] = positional_cutoffs


    # --- 3. Combine and Apply Relevance Filter to all disqualified players (IR + SMF) ---
    disqualified_sources = [df_excluded_ir]
    if not df_excluded_single_matchup.empty:
        disqualified_sources.append(df_excluded_single_matchup[['Roster_ID', 'Position', 'Player Name', 'Median Points', 'Reason']])
        
    df_disqualified_all = pd.concat(disqualified_sources, ignore_index=True)
    
    if df_disqualified_all.empty:
        df_excluded_filtered = pd.DataFrame([], columns=['Roster_ID', 'Position', 'Player Name', 'Median Points', 'Reason'])
    else:
        df_disqualified_all['Median Points'] = pd.to_numeric(df_disqualified_all['Median Points'], errors='coerce')

        relevant_disqualified_list = []
        
        for index, row in df_disqualified_all.iterrows():
            roster_id = row['Roster_ID']
            median_points = row['Median Points']
            
            overall_cutoff = relevant_player_scores_by_team.get(roster_id, -1.0) 
            
            pos = row['Position'] 
            team_positional_cutoffs = positional_cutoffs_by_team.get(roster_id, {})
            positional_floor = team_positional_cutoffs.get(pos, overall_cutoff)
            
            final_cutoff = max(overall_cutoff, positional_floor)

            # Apply the competitiveness check using the player's actual median (or 0.0 for never-scored IR)
            if median_points >= final_cutoff: 
                relevant_disqualified_list.append(row.to_dict())
                        
        df_excluded_filtered = pd.DataFrame(relevant_disqualified_list, columns=df_disqualified_all.columns)


    # --- 4. Loop through sorted teams and output ---
    final_output = []
    for roster_id in sorted_roster_ids:
        team_df = df_optimal[df_optimal['Roster_ID'] == roster_id].copy()
        
        if team_df.empty:
            continue
            
        team_name = team_df['Team Name'].iloc[0]

        # 1. Detail Rows (Optimal Lineup)
        detail_rows = team_df[['Team Name', 'Position', 'Player_Name', 'Median_Points']].copy()
        detail_rows.rename(columns={'Player_Name': 'Player Name', 'Median_Points': 'Median Points'}, inplace=True)
        
        detail_rows['Position_Category'] = pd.Categorical(detail_rows['Position'], categories=category_order, ordered=True)
        detail_rows = detail_rows.sort_values(by=['Position_Category', 'Median Points'], ascending=[True, False])
        detail_rows['Slot_Index'] = detail_rows.groupby('Position_Category', observed=True).cumcount()
        detail_rows = detail_rows.sort_values(by=['Position_Category', 'Slot_Index']).drop(columns=['Position_Category', 'Slot_Index'])
        detail_rows = detail_rows[FINAL_COLUMNS] 
        
        final_output.append(detail_rows)
        
        # 2. Summary Row (Total)
        total_median = team_df['Median_Points'].sum()
        summary_row = pd.DataFrame([{
            'Team Name': team_name,
            'Position': 'TOTAL',
            'Player Name': '',
            'Median Points': total_median
        }], columns=FINAL_COLUMNS)
        final_output.append(summary_row)

        # 3. Backup Rows
        backup_df = df_remaining[df_remaining['Roster_ID'] == roster_id].copy()
        
        if not backup_df.empty:
            for pos in backup_positions:
                top_backup = backup_df[backup_df['Position'] == pos].head(1)
                
                if not top_backup.empty:
                    backup_data = top_backup.iloc[0]
                    
                    backup_row = pd.DataFrame([{
                        'Team Name': team_name,
                        'Position': f'BACKUP {pos}',
                        'Player Name': backup_data['Player_Name'],
                        'Median Points': backup_data['Median_Points']
                    }], columns=FINAL_COLUMNS)
                    final_output.append(backup_row)
            
        # 4. Disqualified Players
        team_excluded = df_excluded_filtered[df_excluded_filtered['Roster_ID'] == roster_id].copy()
        
        if not team_excluded.empty:
            disqualified_list = team_excluded.copy()
            disqualified_list['Position_Category'] = pd.Categorical(disqualified_list['Position'], categories=backup_positions, ordered=True)
            disqualified_list['Reason_Category'] = disqualified_list['Reason'].apply(lambda x: 0 if x == 'IR Status' else 1)
            disqualified_list = disqualified_list.sort_values(by=['Reason_Category', 'Position_Category'], ascending=[True, True])

            for index, player in disqualified_list.iterrows():
                # Display the calculated median for the IR player
                display_points = player['Median Points']

                disqualified_row = pd.DataFrame([{
                    'Team Name': team_name,
                    'Position': f'{player["Reason"].upper()}',
                    'Player Name': player['Player Name'] + f' ({player["Position"]})', 
                    'Median Points': display_points
                }], columns=FINAL_COLUMNS)
                final_output.append(disqualified_row)
            
        # Add an empty row for separation (Team Name is blank)
        final_output.append(pd.DataFrame([{
            'Team Name': '', 
            'Position': np.nan, 
            'Player Name': np.nan, 
            'Median Points': np.nan
        }], columns=FINAL_COLUMNS))


    df_final_output = pd.concat(final_output, ignore_index=True)
    
    # Output to CSV
    df_final_output.to_csv(OUTPUT_CSV_FILE, index=False)
    
    print(f"\n✅ Success! Optimal lineups, backups, and filtered disqualified players saved to {OUTPUT_CSV_FILE}")
    print("The CSV is now sorted by team TOTAL score and includes filtered disqualified players.")
    
    try:
        if df_final_output.empty:
            return None 
            
        df_final_output['Team Name'] = df_final_output['Team Name'].astype(str)
        separator_rows = df_final_output[df_final_output['Team Name'] == '']
        
        if separator_rows.empty:
            end_index = len(df_final_output)
        else:
            first_separator_index = separator_rows.index.min()
            end_index = first_separator_index + 1 
        
        preview_data = df_final_output.head(end_index)
        
        return preview_data.to_markdown(index=False, floatfmt=".2f")
    except Exception as e:
        print(f"\nERROR: Failed to generate table preview (CSV file should still be correct): {e}")
        return None 


# --- MAIN EXECUTION ---

if __name__ == '__main__':
    results_load = load_maps()
    
    if results_load is not None:
        position_map, name_map, roster_map, ir_players_dict, full_position_map = results_load
    else:
        print("\nScript failed due to missing files or data loading errors.")
        exit()

    results_process = process_matchup_data(position_map, name_map, roster_map, full_position_map)
    
    if results_process is not None:
        df_median_scores, df_excluded_single_matchup, player_to_roster = results_process
    else:
        print("\nError: Failed to process matchup data.")
        exit()

    if df_median_scores is not None and not df_median_scores.empty:
        df_optimal_lineup, df_remaining_players = select_optimal_lineup(df_median_scores)
        
        if not df_optimal_lineup.empty:
            # Pass the full df_median_scores to the formatter for the IR score lookup
            preview = format_output_csv(df_optimal_lineup, df_remaining_players, roster_map, ir_players_dict, df_excluded_single_matchup, player_to_roster, df_median_scores)
            if preview:
                print("\n--- PREVIEW OF OPTIMAL LINEUP CSV (Trade Logic & All Filters Applied) ---")
                print(preview)
        else:
            print("\nError: Could not determine any optimal lineups.")
    else:
        print("\nError: Failed to calculate median scores or no active players remain after filtering.")