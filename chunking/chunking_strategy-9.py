#!/usr/bin/env python3

import json
import struct
import shutil
from pathlib import Path
from collections import defaultdict
import numpy as np
from datetime import datetime
from sklearn.cluster import KMeans
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt

def read_images_txt(path):
    images = {}
    images_txt = Path(path) / "images.txt"
    
    if not images_txt.exists():
        return None
    
    print(f"Reading images from text file: {images_txt}")
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
                
                if line_count % 1000 == 0:
                    print(f"  Loaded {line_count} images...")
                
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
    
    print(f"\nSuccessfully loaded {len(images)} images from text file")
    return images

def read_images_bin(path):
    images = {}
    MAX_NAME_LENGTH = 512
    MAX_POINTS2D = 50000
    
    file_size = Path(path).stat().st_size
    print(f"Reading images from {path} (file size: {file_size / (1024*1024):.2f} MB)")
    
    with open(path, 'rb') as f:
        header = f.read(8)
        if len(header) < 8:
            raise ValueError("Invalid images.bin file: cannot read header")
        
        num_reg_images = struct.unpack('<Q', header)[0]
        print(f"Found {num_reg_images} registered images")
        
        if num_reg_images > 100000:
            print(f"Warning: Very large number of images ({num_reg_images}), this may take a while")
        
        for idx in range(num_reg_images):
            if (idx + 1) % 1000 == 0:
                print(f"  Processed {idx + 1}/{num_reg_images} images...")
            
            try:
                image_id_bytes = f.read(4)
                if len(image_id_bytes) < 4:
                    print(f"Warning: Unexpected end of file at image {idx + 1}")
                    break
                image_id = struct.unpack('<I', image_id_bytes)[0]
                
                rotation_bytes = f.read(32)
                if len(rotation_bytes) < 32:
                    break
                qw, qx, qy, qz = struct.unpack('<dddd', rotation_bytes)
                
                translation_bytes = f.read(24)
                if len(translation_bytes) < 24:
                    break
                tx, ty, tz = struct.unpack('<ddd', translation_bytes)
                
                camera_id_bytes = f.read(4)
                if len(camera_id_bytes) < 4:
                    break
                camera_id = struct.unpack('<I', camera_id_bytes)[0]
                
                name_length_bytes = f.read(8)
                if len(name_length_bytes) < 8:
                    break
                name_length = struct.unpack('<Q', name_length_bytes)[0]
                
                if name_length > MAX_NAME_LENGTH:
                    print(f"Error: Image {image_id} has invalid name length ({name_length} bytes), max allowed is {MAX_NAME_LENGTH}")
                    print(f"  This usually indicates corrupted data. Skipping rest of file.")
                    break
                
                if name_length <= 0:
                    print(f"Error: Invalid name length {name_length} for image {image_id}")
                    break
                
                name_bytes = f.read(name_length)
                if len(name_bytes) < name_length:
                    print(f"Error: Could not read full name for image {image_id} (expected {name_length}, got {len(name_bytes)})")
                    break
                
                try:
                    name = name_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
                except:
                    name = name_bytes[:100].decode('utf-8', errors='ignore')
                
                num_points2D_bytes = f.read(8)
                if len(num_points2D_bytes) < 8:
                    break
                num_points2D = struct.unpack('<Q', num_points2D_bytes)[0]
                
                if num_points2D > MAX_POINTS2D:
                    points2D_size = 24 * num_points2D
                    if points2D_size > 100 * 1024 * 1024:
                        print(f"Warning: Image {image_id} has {num_points2D} points (would skip {points2D_size / (1024*1024):.1f} MB), skipping")
                        break
                    f.seek(points2D_size, 1)
                else:
                    points2D_size = 24 * num_points2D
                    f.seek(points2D_size, 1)
                
                images[image_id] = {
                    'name': name,
                    'camera_id': camera_id,
                    'rotation': (qw, qx, qy, qz),
                    'translation': (tx, ty, tz)
                }
                
            except MemoryError as e:
                print(f"\nMemory error at image {idx + 1} (image_id: {image_id if 'image_id' in locals() else 'unknown'}): {e}")
                print(f"Successfully loaded {len(images)} images before error")
                if len(images) > 0:
                    print(f"Warning: Only partial data loaded. Continuing with {len(images)} images.")
                    return images
                else:
                    raise
            except struct.error as e:
                print(f"\nStruct error at image {idx + 1}: {e}")
                print(f"Successfully loaded {len(images)} images before error")
                break
            except Exception as e:
                print(f"\nUnexpected error at image {idx + 1}: {type(e).__name__}: {e}")
                print(f"Successfully loaded {len(images)} images before error")
                break
        
        print(f"\nSuccessfully loaded {len(images)} images from binary file")
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


def chunk_by_temporal_order(images_dict, num_chunks, overlap_ratio=0.1):
    # Sort by (frame, left-then-right) so temporal chunks keep left/right pairs together
    sorted_items = sorted(images_dict.items(), key=lambda x: _temporal_sort_key(x[1]['name']))
    total = len(sorted_items)
    chunk_size = int(total / num_chunks)
    overlap = int(chunk_size * overlap_ratio)
    
    chunks = []
    for i in range(num_chunks):
        start = max(0, i * chunk_size - overlap if i > 0 else 0)
        end = min(total, (i + 1) * chunk_size + overlap if i < num_chunks - 1 else total)
        chunk_images = {img_id: img_data for img_id, img_data in sorted_items[start:end]}
        chunks.append({
            'chunk_id': i,
            'image_ids': list(chunk_images.keys()),
            'image_names': [img['name'] for img in chunk_images.values()],
            'num_images': len(chunk_images),
            'start_idx': start,
            'end_idx': end
        })
    return chunks
    
def point_to_voronoi_boundary_distance(point, vor, region_index):
    region = vor.regions[region_index]
    if -1 in region:
        return np.inf
    verticies = vor.vertices[region]
    distances = np.linalg.norm(vertices-point,axis=1)
    return np.min(distances)
    
def chunk_by_spatial_volume_with_voronoi_overlap(images_dict,num_chunks,overlap_distance):
    translations = []
    images_list = list(images_dict.items())
    
    for img_id, img_data in images_list:
        tx,ty,tz=img_data['translation']
        translations.append((img_id,tx,ty,tz))
        
    translations = np.array(translations)
    coords = translations[:,1:4]
    
    kmeans = KMeans(n_clusters=num_chunks,random_state=42,n_init=10)
    labels = kmeans.fit_predict(coords)
    cluster_centers = kmeans.cluster_centers_
    
    vor = Voronoi(cluster_centers)
    
    image_chunk_map = {img_id: [] for img_id, _, _, _ in translations}
    
    print(f"Images assigned to initial chunks...")
    
    for i, (img_id, x, y, z) in enumerate(translations):
        distances_to_vertices = [
          point_to_voronoi_boundary_distance((x,y),vor,region)
          for region in range(len(vor.regions)) if vor.regions[region]!=[] and i in vor.point_region
        ]
        min_distance_to_boundary = np.min(distances_to_vertices) if distances_to_vertices else np.inf
        
        if min_distance_to_boundary <= overlap_distance:
            for cluster_idx in range(num_chunks):
                image_chunk_map[img_id].append(cluster_idx)
        else:
            nearest_cluster = labels[i]
            image_chunk_map[img_id].append(nearest_cluster)
            
    print(f"Cluster boundaries blended...")
              
    chunks = []
    for i in range(num_chunks):
        chunk_image_ids = [img_id for img_id, clusters in image_chunk_map.items() if i in clusters]
        chunk_images = {img_id: images_dict[img_id] for img_id in chunk_image_ids}
        chunks.append({
            'chunk_id': i,
            'image_ids':chunk_image_ids,
            'image_names':[images_dict[img_id]['name'] for img_id in chunk_image_ids],
            'num_images':len(chunk_image_ids),
            'center':cluster_centers[i].tolist()
        })
        
    return chunks

def chunk_by_spatial_volume(images_dict, num_chunks):
    translations = []
    image_list = list(images_dict.items())
    
    for img_id, img_data in image_list:
        tx, ty, tz = img_data['translation']
        translations.append((img_id, tx, ty, tz))
    
    translations = np.array(translations)
    coords = translations[:, 1:4]
    
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=num_chunks, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)
    
    chunks = []
    for i in range(num_chunks):
        mask = labels == i
        chunk_image_ids = translations[mask, 0].astype(int).tolist()
        chunk_images = {img_id: images_dict[img_id] for img_id in chunk_image_ids}
        n = len(chunk_image_ids)
        if n < 10:
            print(f"WARNING: Spatial chunk {i} has only {n} images; consider using more chunks or temporal strategy")
        chunks.append({
            'chunk_id': i,
            'image_ids': chunk_image_ids,
            'image_names': [images_dict[img_id]['name'] for img_id in chunk_image_ids],
            'num_images': n,
            'center': kmeans.cluster_centers_[i].tolist()
        })
    return chunks

def find_images_directory(base_dense_dir):
    """Find the images directory, checking multiple possible locations."""
    base_path = Path(base_dense_dir)
    
    # Try common locations
    possible_paths = [
        base_path / "images",
        base_path.parent / "images",
        base_path.parent.parent / "images",
    ]
    
    for img_dir in possible_paths:
        if img_dir.exists() and img_dir.is_dir():
            return img_dir
    
    return None


def write_chunk_sparse_txt(sparse_dir, sparse_chunk_dir, chunk_image_ids):
    """
    Write chunk-specific sparse model (images + points3D subset) so dense reconstruction
    only sees this chunk's images and 3D points. Requires sparse_dir to have .txt files;
    create them with: colmap model_converter --input_path <sparse_dir> --output_path <sparse_dir> --output_type TXT
    """
    sparse_path = Path(sparse_dir)
    out_path = Path(sparse_chunk_dir)
    chunk_ids = set(chunk_image_ids)
    
    images_txt = sparse_path / "images.txt"
    points3D_txt = sparse_path / "points3D.txt"
    cameras_txt = sparse_path / "cameras.txt"
    cameras_bin = sparse_path / "cameras.bin"
    
    if not images_txt.exists():
        return False, "images.txt not found (run colmap model_converter to create TXT)"
    
    # --- Points3d: copy full ---
    if points3D_txt.exists():
        shutil.copy2(points3D_txt, out_path / "points3D.txt")
    elif points3D_bin.exists():
        shutil.copy2(points3D_bin, out_path / "points3D.bin")
        
    # --- images: copy full ---
    if images_txt.exists():
        shutil.copy2(images_txt, out_path / "images.txt")
    elif images_bin.exists():
        shutil.copy2(images_bin, out_path / "images.bin")
    
    # --- Cameras: copy full (same intrinsics for all chunks) ---
    if cameras_txt.exists():
        shutil.copy2(cameras_txt, out_path / "cameras.txt")
    elif cameras_bin.exists():
        shutil.copy2(cameras_bin, out_path / "cameras.bin")
    
    if not points3D_txt.exists():
        return True, "chunk sparse (images.txt + cameras) written; points3D.txt not found (run model_converter or copy points3D.bin manually)"
    return True, "chunk sparse (TXT) written"


def create_chunk_workspace(base_dense_dir, chunk_info, sparse_dir, output_base, copy_files=False, split_sparse=True):
    """Create workspace for a chunk, linking or copying images as needed."""
    chunk_id = chunk_info['chunk_id']
    chunk_dense_dir = Path(output_base) / f"chunk_{chunk_id:02d}" / "dense"
    chunk_dense_dir.mkdir(parents=True, exist_ok=True)
    
    sparse_chunk_dir = chunk_dense_dir / "sparse"
    sparse_chunk_dir.mkdir(parents=True, exist_ok=True)
    
    images_chunk_dir = chunk_dense_dir / "images"
    images_chunk_dir.mkdir(parents=True, exist_ok=True)
    
    left_chunk_dir = images_chunk_dir / "left"
    right_chunk_dir = images_chunk_dir / "right"
    left_chunk_dir.mkdir(exist_ok=True)
    right_chunk_dir.mkdir(exist_ok=True)
    
    # Find the original images directory
    original_images_dir = find_images_directory(base_dense_dir)
    if original_images_dir is None:
        print(f"WARNING: Could not find images directory near {base_dense_dir}")
        original_images_dir = Path(base_dense_dir) / "images"
    
    if not original_images_dir.exists():
        print(f"WARNING: Images directory does not exist: {original_images_dir}")
        return chunk_dense_dir
    
    print(f"\n=== Processing chunk {chunk_id} ===")
    print(f"Found images directory: {original_images_dir}")
    print(f"Mode: {'Copying' if copy_files else 'Linking'} images")
    
    left_linked = 0
    right_linked = 0
    left_failed = 0
    right_failed = 0
    missing_left = []
    missing_right = []
    
    # Debug: show what we're looking for (for first chunk or small chunks)
    if chunk_id == 0 or len(chunk_info['image_names']) <= 10:
        print(f"Looking for {len(chunk_info['image_names'])} images in chunk {chunk_id}")
        print(f"First few image names from sparse reconstruction:")
        for img_name in chunk_info['image_names'][:5]:
            print(f"  - '{img_name}'")
    
    # Debug: show actual files available (for first chunk only)
    if chunk_id == 0:
        left_files = sorted([f.name for f in (original_images_dir / "left").glob("*.*")]) if (original_images_dir / "left").exists() else []
        right_files = sorted([f.name for f in (original_images_dir / "right").glob("*.*")]) if (original_images_dir / "right").exists() else []
        print(f"Found {len(left_files)} files in left/ directory")
        if left_files:
            print(f"Sample left files: {left_files[:3]} ... {left_files[-3:] if len(left_files) > 3 else ''}")
        print(f"Found {len(right_files)} files in right/ directory")
        if right_files:
            print(f"Sample right files: {right_files[:3]} ... {right_files[-3:] if len(right_files) > 3 else ''}")
    
    def link_or_copy_image(source, target, copy_files):
        """Link or copy an image file, handling errors."""
        try:
            if target.exists():
                return True  # Already exists
            
            if copy_files:
                shutil.copy2(source, target)
            else:
                target.symlink_to(source.absolute())
            return True
        except OSError as e:
            # Try copying if symlink fails (e.g., on Windows or cross-filesystem)
            if not copy_files:
                try:
                    shutil.copy2(source, target)
                    return True
                except Exception as e2:
                    print(f"ERROR: Failed to copy {source.name}: {e2}")
                    return False
            else:
                print(f"ERROR: Failed to copy {source.name}: {e}")
                return False
        except Exception as e:
            print(f"ERROR: Unexpected error with {source.name}: {e}")
            return False
    
    for img_name in chunk_info['image_names']:
        # Strip path prefixes like "left/" or "right/" if present
        # Handle cases like "right/right_0746.jpg" -> "right_0746.jpg"
        clean_img_name = img_name
        if '/' in img_name:
            # Extract just the filename from path
            parts = img_name.split('/')
            clean_img_name = parts[-1]  # Get the last part (filename)
        
        # Try different name patterns to handle various naming conventions.
        # Keep left_/right_ in filenames for MultiViewTracks (tracks.pkl links by image name).
        if clean_img_name.startswith('left_'):
            base_name = clean_img_name.replace('left_', '')
            source_paths = [
                original_images_dir / "left" / base_name,
                original_images_dir / "left" / clean_img_name,
                original_images_dir / "left" / clean_img_name.lower(),
                original_images_dir / "left" / base_name.lower(),
            ]
            target = left_chunk_dir / clean_img_name  # keep left_0001.jpg for MultiViewTracks
            linked = False
            for source in source_paths:
                if source.exists():
                    if link_or_copy_image(source, target, copy_files):
                        left_linked += 1
                        linked = True
                    else:
                        left_failed += 1
                    break
            if not linked:
                missing_left.append(img_name)
        elif clean_img_name.startswith('right_'):
            base_name = clean_img_name.replace('right_', '')
            source_paths = [
                original_images_dir / "right" / base_name,
                original_images_dir / "right" / clean_img_name,
                original_images_dir / "right" / clean_img_name.lower(),
                original_images_dir / "right" / base_name.lower(),
            ]
            target = right_chunk_dir / clean_img_name  # keep right_0001.jpg for MultiViewTracks
            linked = False
            for source in source_paths:
                if source.exists():
                    if link_or_copy_image(source, target, copy_files):
                        right_linked += 1
                        linked = True
                    else:
                        right_failed += 1
                    break
            if not linked:
                missing_right.append(img_name)
        else:
            # Image name doesn't have left_/right_ prefix - try both directories
            source_paths = [
                original_images_dir / "left" / clean_img_name,
                original_images_dir / "right" / clean_img_name,
                original_images_dir / "left" / clean_img_name.lower(),
                original_images_dir / "right" / clean_img_name.lower(),
            ]
            linked = False
            for source in source_paths:
                if source.exists():
                    if "left" in str(source):
                        target = left_chunk_dir / clean_img_name
                    else:
                        target = right_chunk_dir / clean_img_name
                    
                    if link_or_copy_image(source, target, copy_files):
                        if "left" in str(source):
                            left_linked += 1
                        else:
                            right_linked += 1
                        linked = True
                    else:
                        if "left" in str(source):
                            left_failed += 1
                        else:
                            right_failed += 1
                    break
            if not linked:
                # Try to guess based on path prefix in original name
                if 'left' in img_name.lower() or '/left/' in img_name:
                    missing_left.append(img_name)
                elif 'right' in img_name.lower() or '/right/' in img_name:
                    missing_right.append(img_name)
    
    print(f"Chunk {chunk_id}: Successfully {'copied' if copy_files else 'linked'} {left_linked} left images, {right_linked} right images")
    
    if left_failed > 0 or right_failed > 0:
        print(f"WARNING: Failed to {'copy' if copy_files else 'link'} {left_failed} left and {right_failed} right images")
    
    if missing_left or missing_right:
        print(f"WARNING: Could not find {len(missing_left)} left and {len(missing_right)} right images")
        if len(missing_left) <= 10:
            print(f"Missing left images: {missing_left}")
        else:
            print(f"Missing left images (showing first 10): {missing_left[:10]}")
        if len(missing_right) <= 10:
            print(f"Missing right images: {missing_right}")
        else:
            print(f"Missing right images (showing first 10): {missing_right[:10]}")
        print(f"DEBUG: This suggests the image names in sparse reconstruction don't match actual filenames.")
        print(f"DEBUG: Please check the image names in sparse/0/images.txt or images.bin")
    
    # Per-chunk sparse: write subset so dense reconstruction only sees this chunk's images/points
    chunk_image_ids = set(chunk_info.get('image_ids', []))
    if split_sparse and (Path(sparse_dir) / "images.txt").exists():
        ok, msg = write_chunk_sparse_txt(sparse_dir, sparse_chunk_dir, chunk_image_ids)
        if ok:
            print(f"Chunk {chunk_id}: {msg}")
        else:
            print(f"Chunk {chunk_id}: WARNING {msg}; linking full sparse instead")
            split_sparse = False
    if not split_sparse:
        # Link or copy full sparse (legacy: each chunk gets same full model)
        for bin_file in ['cameras.bin', 'images.bin', 'points3D.bin']:
            source = Path(sparse_dir) / bin_file
            if source.exists():
                target = sparse_chunk_dir / bin_file
                if not target.exists():
                    try:
                        target.symlink_to(source.absolute())
                    except OSError:
                        try:
                            shutil.copy2(source, target)
                        except Exception as e:
                            print(f"WARNING: Could not link or copy {bin_file}: {e}")
        if chunk_id == 0:
            print(f"Chunk {chunk_id}: Using full sparse model in each chunk. For per-chunk sparse, run: colmap model_converter --input_path <sparse_dir> --output_path <sparse_dir> --output_type TXT")
    
    stereo_dir = chunk_dense_dir / "stereo"
    stereo_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ['depth_maps/left', 'depth_maps/right', 'normal_maps/left', 'normal_maps/right', 'consistency_graphs/left', 'consistency_graphs/right']:
        (stereo_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    return chunk_dense_dir

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Create chunking strategy for dense reconstruction')
    parser.add_argument('--sparse_dir', type=str, required=True, help='Path to sparse reconstruction directory')
    parser.add_argument('--dense_dir', type=str, required=True, help='Path to dense directory with images')
    parser.add_argument('--num_chunks', type=int, required=True, help='Number of chunks to create')
    parser.add_argument('--strategy', type=str, choices=['temporal', 'spatial'], default='temporal', help='Chunking strategy')
    parser.add_argument('--overlap_ratio', type=float, default=0.1, help='Overlap ratio for temporal chunking')
    parser.add_argument('--output_base', type=str, required=True, help='Base directory for chunk outputs')
    parser.add_argument('--create_workspaces', action='store_true', help='Create chunk workspace directories')
    parser.add_argument('--copy_files', action='store_true', help='Copy image files instead of creating symlinks (useful if symlinks fail)')
    parser.add_argument('--split_sparse', action='store_true', dest='split_sparse', default=False, help='Use full sparse model in each chunk (legacy). Default is to write per-chunk sparse when images.txt exists (run colmap model_converter first).')
    
    args = parser.parse_args()
    
    sparse_path = Path(args.sparse_dir)
    images_bin = sparse_path / "images.bin"
    images_txt = sparse_path / "images.txt"
    
    print(f"Reading sparse reconstruction from {sparse_path}")
    
    images_dict = None
    
    if images_txt.exists():
        print("Found images.txt - using text format (more memory efficient)")
        images_dict = read_images_txt(sparse_path)
    
    if images_dict is None or len(images_dict) == 0:
        if images_bin.exists():
            print("Using binary format images.bin")
            images_dict = read_images_bin(images_bin)
        else:
            print(f"Error: Neither images.bin nor images.txt found in {sparse_path}")
            return
    
    if len(images_dict) == 0:
        print("Error: No images found in reconstruction")
        return
    
    print(f"Found {len(images_dict)} registered images")
    
    if args.strategy == 'temporal':
        print(f"Creating {args.num_chunks} temporal chunks with {args.overlap_ratio*100}% overlap")
        chunks = chunk_by_temporal_order(images_dict, args.num_chunks, args.overlap_ratio)
    else:
        print(f"Creating {args.num_chunks} spatial chunks using K-means clustering")
        chunks = chunk_by_spatial_volume_with_voronoi_overlap(images_dict, args.num_chunks, args.overlap_ratio)
    
    output_base = Path(args.output_base)
    output_base.mkdir(parents=True, exist_ok=True)
    
    chunks_info = {
        'strategy': args.strategy,
        'num_chunks': args.num_chunks,
        'total_images': len(images_dict),
        'timestamp': datetime.now().isoformat(),
        'chunks': []
    }
    
    print(f"\n{'='*60}")
    print(f"Creating {len(chunks)} chunks...")
    print(f"{'='*60}\n")
    
    successful_chunks = 0
    failed_chunks = []
    
    for chunk in chunks:
        chunk_summary = {
            'chunk_id': chunk['chunk_id'],
            'num_images': chunk['num_images'],
            'image_names': chunk['image_names'][:5] + ['...'] if len(chunk['image_names']) > 5 else chunk['image_names']
        }
        chunks_info['chunks'].append(chunk_summary)
        
        if args.create_workspaces:
            try:
                chunk_dir = create_chunk_workspace(
                    args.dense_dir, 
                    chunk, 
                    sparse_path, 
                    args.output_base,
                    copy_files=args.copy_files,
                    split_sparse=args.split_sparse
                )
                print(f"✓ Created workspace for chunk {chunk['chunk_id']:02d}: {chunk_dir} ({chunk['num_images']} images)")
                successful_chunks += 1
            except Exception as e:
                error_msg = f"✗ ERROR creating workspace for chunk {chunk['chunk_id']:02d}: {type(e).__name__}: {e}"
                print(error_msg)
                failed_chunks.append((chunk['chunk_id'], str(e)))
                # Continue processing other chunks instead of stopping
                import traceback
                if len(chunks) <= 3:  # Only show full traceback for small number of chunks
                    traceback.print_exc()
    
    output_json = output_base / "chunking_strategy.json"
    with open(output_json, 'w') as f:
        json.dump(chunks_info, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Chunking strategy saved to {output_json}")
    print(f"\nChunk summary:")
    for chunk in chunks:
        print(f"  Chunk {chunk['chunk_id']:02d}: {chunk['num_images']} images")
    
    if args.create_workspaces:
        print(f"\nWorkspace creation: {successful_chunks}/{len(chunks)} chunks created successfully")
        if failed_chunks:
            print(f"\nWARNING: Failed to create {len(failed_chunks)} chunk(s):")
            for chunk_id, error in failed_chunks:
                print(f"  Chunk {chunk_id:02d}: {error}")
        else:
            print("✓ All chunks created successfully!")

if __name__ == '__main__':
    try:
        from sklearn.cluster import KMeans
    except ImportError:
        print("Warning: scikit-learn not available. Spatial chunking will not work.")
        print("Install with: pip install scikit-learn")
    
    main()

