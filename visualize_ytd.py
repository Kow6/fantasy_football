import pandas as pd
import matplotlib.pyplot as plt
import os

# --- CONFIGURATION ---
INPUT_FILE = "ytd_starter_analysis.csv"
OUTPUT_PLOT_FILE = "ytd_starter_analysis_plot.png"
POSITIONS = ['QB', 'RB', 'WR', 'TE'] # Ensure this matches your data columns

def create_stacked_bar_chart():
    """Loads the analysis data and creates a stacked bar chart."""
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: Input file '{INPUT_FILE}' not found. Please ensure the analysis script ran correctly.")
        return

    # 1. Load the data
    df = pd.read_csv(INPUT_FILE)

    # 2. Sort the data by Total Starter Points for cleaner visualization
    # We want the highest scoring team to be at the top of the chart
    df = df.sort_values(by='Total Starter Points', ascending=False)
    
    # Set the 'Team Name' column as the index for plotting
    df.set_index('Team Name', inplace=True)

    # 3. Create the stacked bar chart
    # Use the .plot() function directly on the DataFrame, selecting only the position columns
    plt.style.use('seaborn-v0_8-darkgrid') # Optional: use a nice style for better aesthetics
    
    ax = df[POSITIONS].plot(
        kind='barh',        # 'barh' for horizontal bars, which are better for long team names
        stacked=True,       # Crucial: this stacks the positional scores
        figsize=(12, 8),    # Adjust plot size
        title='Year-To-Date Starter Points by Position',
        xlabel='Total Fantasy Points',
        ylabel='Team Name'
    )

    # 4. Customizing the plot for better readability
    
    # Add Total Score Labels (Optional, but very helpful)
    for i, total in enumerate(df['Total Starter Points']):
        # Annotate the total score at the end of each bar
        ax.text(total + 5, i, f'{total:.1f}', va='center', fontsize=9, fontweight='bold')

    # Move the legend outside the plot
    ax.legend(title='Position', bbox_to_anchor=(1.05, 1), loc='upper left')

    # Adjust layout to prevent labels from being cut off
    plt.tight_layout()

    # 5. Save and Display the plot
    plt.savefig(OUTPUT_PLOT_FILE)
    print(f"\n✅ Plot saved to: {os.path.abspath(OUTPUT_PLOT_FILE)}")
    
    # Display the plot
    plt.show()

if __name__ == "__main__":
    # You must have matplotlib installed: pip install matplotlib
    create_stacked_bar_chart()