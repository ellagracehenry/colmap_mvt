import pickle

# File path
input_file = r"C:\Users\ellag\Downloads\centroids.pkl"

# Load and print the contents of the pickle file
with open(input_file, 'rb') as f:
    centroids_dict = pickle.load(f)

# Print the contents
print("Loaded centroids data:")
print(centroids_dict)

# If you want to explore its structure in a better way:
if isinstance(centroids_dict, dict):
    print("\nKeys in the dictionary:", centroids_dict.keys())  # Print top-level keys of the dictionary
    for key, value in centroids_dict.items():
        print(f"\nKey: {key}")
        print(f"Value: {value}")
else:
    print("\nThe loaded data is not a dictionary. Printing raw content:")
    print(centroids_dict)
