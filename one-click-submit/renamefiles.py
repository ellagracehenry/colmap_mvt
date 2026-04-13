import os
import shutil
import sys
from pathlib import Path
import re


# Function to copy and rename files
def copy_and_rename(src_folder, dst_folder, prefix, sub):
    files = sorted(
        f for f in os.listdir(src_folder)
        if os.path.isfile(os.path.join(src_folder, f)) and not f.startswith('.')
    )

    if not files:
        print("No files found.")
        return

    # Subsample
    files = files[::sub]

    if not files:
        print("No files left after subsampling.")
        return

    # Extract numeric indices
    index_re = re.compile(r'(\d+)(?=\.[^.]+$)')
    parsed = []

    for f in files:
        m = index_re.search(f)
        if not m:
            print(f"Skipping (no index found): {f}")
            continue
        parsed.append((f, int(m.group(1))))

    if not parsed:
        print("No valid indexed files.")
        return

    first_index = parsed[0][1]
    pad_width = len(index_re.search(parsed[0][0]).group(1))

    print(f"First original index: {first_index}")
    print(f"Zero padding width: {pad_width}")

    for file_name, original_idx in parsed:
        new_idx = original_idx - first_index + 1
        new_name = f"{prefix}_{new_idx:0{pad_width}d}.jpg"

        src_path = os.path.join(src_folder, file_name)
        dst_path = os.path.join(dst_folder, new_name)

        shutil.copy2(src_path, dst_path)
        print(f"Copied: {file_name} -> {dst_path}")
        
        
def main(folder_path_L, folder_path_R, project_dir, extracted_fps, final_fps):
    print("Running renamefiles1")
    print(folder_path_L, folder_path_R, project_dir, extracted_fps, final_fps)
    
    # Determine sampling ratio
    sub=int(extracted_fps/final_fps)
    
    # create images folder 
    img_path=os.path.join(project_dir, "images")
    img_path_L = os.path.join(img_path, "left")
    img_path_R = os.path.join(img_path, "right")

    os.makedirs(img_path_L, exist_ok=True)
    os.makedirs(img_path_R, exist_ok=True)\
    
    copy_and_rename(folder_path_R, img_path_R, "right", sub)
    copy_and_rename(folder_path_L, img_path_L, "left", sub)
    print("Copying and renaming images complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Renaming and re-organizing images for colmap reconstruction')
    parser.add_argument('--folder_path_L', type=str, required=True, help='Path left frames dir')
    parser.add_argument('--folder_path_R', type=str, required=True, help='Path to right frames dir')
    parser.add_argument('--project_dir', type=str, required=True, help='Project directory for reconstruction')
    parser.add_argument('--extracted_fps', type=int, default=3, help='Original FPS of synced & extracted images')
    parser.add_argument('--final_fps', type=int, default=1, help='Overlap ratio for temporal chunking')

    args = parser.parse_args()
    
    main(
        args.folder_path_L,
        args.folder_path_R,
        args.project_dir,
        args.extracted_fps,
        args.final_fps,
    )