import csv
import os
import numpy as np
import pandas as pd
import subprocess
import json
import struct
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import re
import argparse

def read_images_txt(path):
    
    images = {}
    images_txt = Path(path) / "images.txt"
    
    if not images_txt.exists():
        return None
    
    with open(images_txt, 'r') as f:
        lines = f.readlines()
        i = 0
        line_count = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                i += 1
                continue
            
            parts = line.split()
            
            # Image line must have at least 10 parts: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID IMAGE_NAME
            if len(parts) < 10:
                # This might be a 2D point line (X Y or X Y POINT3D_ID), skip it
                i += 1
                continue
            
            try:
                # Try to parse as image line
                # COLMAP image line: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID IMAGE_NAME
                # Image name is a single token (e.g. left_0001.jpg or left/left_0001.jpg).
                # Using parts[9] only avoids pulling in 2D point data if format varies.
                image_id = int(parts[0])
                qw = float(parts[1])
                qx = float(parts[2])
                qy = float(parts[3])
                qz = float(parts[4])
                tx = float(parts[5])
                ty = float(parts[6])
                tz = float(parts[7])
                camera_id = int(parts[8])
                name = parts[9].strip()
                # Reject lines where "name" looks like 2D point data (e.g. "-1" or numeric)
                if name == '-1' or (len(name) < 4 and name.replace('.', '').replace('-', '').isdigit()):
                    i += 1
                    continue
                # Reject if it looks like raw numbers (2D point line misread as image line)
                if name.replace('.', '').replace('-', '').replace(' ', '').isdigit():
                    i += 1
                    continue
                
                images[image_id] = {
                    'name': name,
                    'camera_id': camera_id,
                    'rotation': (qw, qx, qy, qz),
                    'translation': (tx, ty, tz)
                }
                line_count += 1
                
                i += 1
                
                # Skip 2D point lines that follow the image line
                # 2D point lines have format: X Y [POINT3D_ID] (2 or 3 parts, all numeric)
                while i < len(lines):
                    next_line = lines[i].strip()
                    
                    # Empty line or comment means next image
                    if not next_line or next_line.startswith('#'):
                        break
                    
                    next_parts = next_line.split()
                    
                    # 2D point lines have 2 or 3 parts, all numeric (except possibly the third)
                    if len(next_parts) == 2 or len(next_parts) == 3:
                        try:
                            # Check if first two are numeric (X, Y coordinates)
                            float(next_parts[0])
                            float(next_parts[1])
                            # If third part exists, it might be point3D_id (could be int or -1)
                            if len(next_parts) == 3:
                                try:
                                    int(next_parts[2])
                                except ValueError:
                                    # Not a valid 2D point line, probably next image
                                    break
                            # This is a 2D point line, skip it
                            i += 1
                            continue
                        except (ValueError, IndexError):
                            # Not numeric, probably next image line
                            break
                    else:
                        # Not 2 or 3 parts, probably next image line
                        break
                
            except (ValueError, IndexError) as e:
                # Not a valid image line, skip it
                i += 1
                continue
    
    return images

def _temporal_sort_key(name):
    """Extract (frame_number, side) so left_0001 and right_0001 sort together by time.
    MultiViewTracks needs left/right pairs at the same frame in the same chunk."""
    import re
    base = name.split('/')[-1] if '/' in name else name  # left_0001.jpg or right_0001.jpg
    m = re.search(r'(?:left_|right_)?(\d+)', base, re.IGNORECASE)
    frame = int(m.group(1)) if m else 0
    side = 0 if 'left' in name.lower() else 1
    return (frame, side, name)

def extract_frame_number(image_name):
    base = image_name.split('/')[-1] #split image name at the split
    m = re.search(r'(\d+)(?=\.\w+$)', base)
    if not m:
        raise ValueError(f"Could not extract frame number from {image_name}")
    return int(m.group(1))


def find_contiguous_ranges(sorted_frames): #given a sorted list of frames
    ranges = [] #initialise empty list
    if not sorted_frames: #if no frames return an empty list
        return ranges

    start = prev = sorted_frames[0] #begin the first range at the first frame

    for frame in sorted_frames[1:]: #loop over remaining frames starting at the second position
        if frame == prev + 3:  # because extr_fps = 3, a sequence is continuous
            prev = frame #extent current range
        else: #if a gap is found, close range and save
            ranges.append((start, prev))
            start = prev = frame #and start a new range

    ranges.append((start, prev)) #save final range
    return ranges


def main():
    parser = argparse.ArgumentParser(description = 'Analyse sparse point cloud subfolders')
    parser.add_argument('--sparse_path', type = str, required=True, help='Directory containing sparse submodels')
    parser.add_argument('--first_image', type=int, required=True, help='The number of the first image in images folder, usually 1 (i.e. left_0001.jpg)')
    parser.add_argument('--last_image', type=int, required=True, help='The number of the last image in images folder, (e.g. 3664 for left_3664.jpg)')
    parser.add_argument('--fps', type=int, required=True, help='The fps your image set is in')

    if len(os.sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    sparse_path = args.sparse_path
    first_left = args.first_image
    last_left = args.last_image
    fps = args.fps

    if fps == 3:
        extr_fps = 1
    else:
        extr_fps = 3

    exp_frames = ((last_left - first_left) // extr_fps) + 1

    sparse_path = Path(sparse_path)

    print(f"Reading sparse reconstruction from {sparse_path}...")
    

    folders = [p for p in sparse_path.iterdir() if p.is_dir()]
    num_folders = len(folders)
    print(f"There are {num_folders} submodels at {sparse_path}")
 
    summary_dict = {}

    for submodel_dir in folders:
        if submodel_dir.is_dir():
            print(f"Processing submodel: {submodel_dir.name}")

            output_path = submodel_dir/"images-list.csv"
            summary_output_path = submodel_dir/"missing_images.csv"
            images_txt = submodel_dir/"images.txt"
        else:
            print(f"Non directory found, exiting...")
            return
        if images_txt.exists():
            print(f"image.txt already exists! Reusing...")
        else:
            print(f"converting images.bin to images.txt...")
            subprocess.run([
                "colmap", "model_converter",
                "--input_path", submodel_dir,
                "--output_path", submodel_dir,
                "--output_type", "TXT"
            ], check=True)


        images_dict = None

        if images_txt.exists():
            images_dict = read_images_txt(submodel_dir)
        else:
            print(f"Error: images.txt not found in {submodel_dir}")

        if len(images_dict) == 0:
            print("Error: No images found in reconstruction")

        print(f"Found {len(images_dict)} registered images in submodel")

        print(f"At {extr_fps} fps, expected {exp_frames*2} images ({exp_frames} in each camera), ranging from frame {first_left} to frame {last_left}")

        if len(images_dict) == exp_frames*2:
            print(f"All images in submodel, exiting...")
            return
        else:
            print(f"~{int(100-(len(images_dict)/(exp_frames*2)*100))}% images missing from submodel, generating report...")

            #Writing summary
            # Sort images temporally
            sorted_items = sorted(images_dict.items(), key=lambda x: _temporal_sort_key(x[1]['name']))

            # Extract frame numbers (only left side to avoid duplicates)
            left_frames = []
            right_frames = []

            for _, img_data in sorted_items:
                name = img_data['name']
                frame = extract_frame_number(name)

                if name.startswith("left/"):
                    left_frames.append(frame)
                elif name.startswith("right/"):
                    right_frames.append(frame)
            
            left_frames = sorted(left_frames)
            right_frames = sorted(right_frames)

            left_count = len(left_frames)
            right_count = len(right_frames)

            left_ranges = find_contiguous_ranges(left_frames)
            right_ranges = find_contiguous_ranges(right_frames)

            left_range_strings = [f"{s}-{e}" for s, e in left_ranges]
            right_range_strings = [f"{s}-{e}" for s, e in right_ranges]

            summary_dict[f"{submodel_dir.name}_left"] = [left_count] + left_range_strings
            summary_dict[f"{submodel_dir.name}_right"] = [right_count] + right_range_strings

            #Writing missing images files

            left_frames_dict ={}
            right_frames_dict={}

            for _, img_data in sorted_items:
                name = img_data['name']
                frame = extract_frame_number(name)
                side = name.split('/')[0]

                if side == "left":
                    left_frames_dict[frame] = name
                elif side == "right":
                    right_frames_dict[frame] = name

            all_frames = sorted(set(left_frames_dict.keys()) | set(right_frames_dict.keys()))

            fieldnames = ["left_name", "left_frame","right_name","right_frame"]

            with open(output_path, mode = 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for frame in all_frames:
                    row = {
                        'left_name': left_frames_dict.get(frame,''),
                        'left_frame': frame if frame in left_frames_dict else '',
                        'right_name': right_frames_dict.get(frame,''),
                        'right_frame': frame if frame in right_frames_dict else ''
                    }
                    writer.writerow(row)

        print(f"Image list writtern to {output_path}")
    
    # Determine max number of rows needed
    max_rows = max(len(v) for v in summary_dict.values())

    # Pad shorter columns
    for key in summary_dict:
        summary_dict[key] += [""] * (max_rows - len(summary_dict[key]))

    # Create DataFrame
    summary_df = pd.DataFrame(summary_dict)

    #Summary csv
    summary_csv_path = sparse_path / "submodel_summary.csv"
    summary_df.to_csv(summary_csv_path, index=False)


    print(f"\u2705 Summary csv written to {summary_csv_path}")
    print(f"\u2705 Individual image lists in each submodel folder")

if __name__ == "__main__":
    main()

