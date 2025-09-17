# load_test.py (Corrected Version)

import asyncio
import time

# Import the function AND the cache duration from your main file
# Make sure to change 'main' to the name of your bot's python file.
from main import get_metrics_text, CACHE_DURATION

# --- CONFIGURATION ---
NUM_USERS = 20 # The number of concurrent users to simulate

async def simulate_user_request(user_id: int):
    """
    This function acts like a single user pressing the 'Metrics' button.
    It calls the same function the bot uses and times how long it takes.
    """
    print(f"User {user_id}: Requesting metrics...")
    start_time = time.time()
    
    await get_metrics_text() 
    
    duration = time.time() - start_time
    print(f"✅ User {user_id}: Got response in {duration:.4f} seconds.")

async def main():
    """
    This is the main driver. It creates and runs all the user
    simulations at the same time using asyncio.gather.
    """
    print(f"--- Simulating {NUM_USERS} users on an EXPIRED cache ---")
    
    tasks = [simulate_user_request(i) for i in range(1, NUM_USERS + 1)]
    
    await asyncio.gather(*tasks)
    
    print("\n--- Simulation finished ---")
    

if __name__ == "__main__":
    # This ensures the cache is populated before the test
    print("Performing a priming run to populate the cache...")
    asyncio.run(get_metrics_text())
    
    # --- THIS IS THE CRUCIAL FIX ---
    # Wait for the cache to expire before running the main test.
    wait_time = CACHE_DURATION + 5 # Wait 5 seconds longer than the cache life
    print(f"Priming run complete. Cache is now fresh. Waiting {wait_time} seconds for it to expire...")
    time.sleep(wait_time)
    
    # Run the main simulation
    asyncio.run(main())