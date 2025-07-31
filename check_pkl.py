import pickle
from pprint import pprint

# Specify the file path
file_path = r"C:\Users\ellag\Downloads\tracks_rightimg.pkl"
#file_path = r"C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\colmap\data\tracks\tracks_i_0_cut.pkl"

with open(file_path, "rb") as f:
    data = pickle.load(f)

    # Step 1: Check if the data is a dictionary or list and print accordingly
    if isinstance(data, dict):
        print("Loaded data is a dictionary:")
        print("Keys in loaded data:", data.keys())  # Print the dictionary keys
    elif isinstance(data, list):
        print("Loaded data is a list:")
        print("First 10 elements in the list:", data[:10])  # Print the first 10 elements (for large lists)
    else:
        print(f"Loaded data is of type {type(data)}")

    # Step 2: Pretty print the loaded data for better readability
    print("\nPretty Printed Data:")
    pprint(data)  # Pretty print the entire loaded data

    # Step 3: Ensure identity is accessed correctly
    if "IDENTITIES" in data:
        identity_key = data["IDENTITIES"][0]  # Get the first identity key directly (no need to convert)
        print("\nIdentity Key:", identity_key)

        # Step 4: Ensure identity key is an integer (if it exists in `IDENTITIES`)
        if isinstance(identity_key, int):
            print(f"Identity key is an integer: {identity_key}")
        else:
            print(f"Identity key is not an integer, it is: {type(identity_key)}")

        # Step 5: Check if identity key exists in the data
        identity_key_str = str(identity_key)  # Convert to string for access
        if identity_key_str in data:
            print(f"Track data found for identity {identity_key_str}")
            track_data = data[identity_key_str]

            # Safe check before printing
            print(f"Track ID: {identity_key_str} | Track Data Type: {type(track_data)}")

            # If it's a dictionary, print the keys
            if isinstance(track_data, dict):
                print("Keys in track data:", track_data.keys())

                # Print only the first 5 values for each key to avoid printing too much data
                print("Track Data Sample (First 5 entries):")
                for key in track_data:
                    print(f"{key}: {track_data[key][:5]}")  # Preview first 5 values for each key

            # If track_data is not a dictionary, print its type and a sample (first 10 elements)
            else:
                print(f"Track Data is of unexpected type: {type(track_data)}")
                print(f"Sample of Track Data (First 10 elements): {track_data[:10] if isinstance(track_data, (list, np.ndarray)) else 'Cannot preview'}")

        else:
            print(f"No track data found for identity key {identity_key_str}")
    else:
        print("No 'IDENTITIES' key found in the data.")

# Print the loaded data (raw output)
print("\nLoaded Data (Raw):")
print(data)
