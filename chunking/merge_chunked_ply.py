#!/usr/bin/env python3

import argparse
import struct
from pathlib import Path
import numpy as np

def read_ply_header(file_path):
    with open(file_path, 'rb') as f:
        header_lines = []
        while True:
            line = f.readline()
            header_lines.append(line)
            if b'end_header' in line:
                break
        return b''.join(header_lines), f.tell()

def read_ply_vertices(file_path):
    header, data_start = read_ply_header(file_path)
    
    num_vertices = None
    for line in header.split(b'\n'):
        if b'element vertex' in line:
            num_vertices = int(line.split()[-1])
            break
    
    if num_vertices is None:
        raise ValueError("Could not find vertex count in PLY header")
    
    vertex_data = []
    with open(file_path, 'rb') as f:
        f.seek(data_start)
        
        for _ in range(num_vertices):
            x = struct.unpack('<f', f.read(4))[0]
            y = struct.unpack('<f', f.read(4))[0]
            z = struct.unpack('<f', f.read(4))[0]
            nx = struct.unpack('<f', f.read(4))[0]
            ny = struct.unpack('<f', f.read(4))[0]
            nz = struct.unpack('<f', f.read(4))[0]
            r = struct.unpack('<B', f.read(1))[0]
            g = struct.unpack('<B', f.read(1))[0]
            b = struct.unpack('<B', f.read(1))[0]
            
            vertex_data.append((x, y, z, nx, ny, nz, r, g, b))
    
    return vertex_data, header

def write_merged_ply(output_path, all_vertices):
    num_vertices = len(all_vertices)
    
    header = (
    "ply\n"
    "format binary_little_endian 1.0\n"
    f"element vertex {num_vertices}\n"
    "property float x\n"
    "property float y\n"
    "property float z\n"
    "property float nx\n"
    "property float ny\n"
    "property float nz\n"
    "property uchar red\n"
    "property uchar green\n"
    "property uchar blue\n"
    "end_header\n"
    )
    
    with open(output_path, 'wb') as f:
        f.write(header.encode('ascii'))
        
        for vertex in all_vertices:
            x, y, z, nx, ny, nz, r, g, b = vertex
            f.write(struct.pack('<ffffffBBB', float(x), float(y), float(z), float(nx), float(ny), float(nz), int(r), int(g), int(b)))
    
    print(f"Merged {num_vertices} vertices into {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Merge chunked PLY point clouds')
    parser.add_argument('--project_dir', type=str, required=True, help='Project directory containing chunks')
    parser.add_argument('--num_chunks', type=int, required=True, help='Number of chunks to merge')
    parser.add_argument('--output', type=str, required=True, help='Output PLY file path')
    parser.add_argument('--deduplicate', action='store_true', help='Remove duplicate points (within 1mm)')
    
    args = parser.parse_args()
    
    project_dir = Path(args.project_dir)
    all_vertices = []
    
    print(f"Reading {args.num_chunks} chunk files...")
    for chunk_id in range(args.num_chunks):
        chunk_file = project_dir / "chunks" / f"chunk_{chunk_id:02d}" / "dense" / f"fused_chunk_{chunk_id}.ply"
        
        if not chunk_file.exists():
            print(f"Warning: {chunk_file} not found, skipping")
            continue
        
        print(f"Reading chunk {chunk_id}: {chunk_file}")
        vertices, _ = read_ply_vertices(chunk_file)
        all_vertices.extend(vertices)
        print(f"  Added {len(vertices)} vertices (total: {len(all_vertices)})")
    
    if args.deduplicate:
    
        print("Deduplicating points in new method...")
        vertices_array = np.array(all_vertices)
        coords = vertices_array[:, :3]
        voxel_size = 0.001
        grid = np.floor(coords/voxel_size).astype(np.int64)
        _, unique_idx = np.unique(grid, axis=0, return_index=True)
        dedup_vertices = vertices_array[unique_idx]
        
        all_vertices = [tuple(v) for v in dedup_vertices]
        
        #print("Deduplicating points method one...")
        #vertices_array = np.array(all_vertices)
        #coords = vertices_array[:, :3]
        
        #from sklearn.neighbors import NearestNeighbors
        #nbrs = NearestNeighbors(n_neighbors=2, algorithm='ball_tree', metric='euclidean')
        #nbrs.fit(coords)
        #distances, indices = nbrs.kneighbors(coords)
        
        #keep_mask = np.ones(len(coords), dtype=bool)
        #for i in range(len(coords)):
        #    if not keep_mask[i]:
        #        continue
        #    close_points = indices[i][distances[i] < 0.001]
        #    keep_mask[close_points[1:]] = False
        
        #all_vertices = [tuple(v) for v in vertices_array[keep_mask]]
        print(f"After deduplication: {len(all_vertices)} vertices")
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nWriting merged PLY to {output_path}...")
    write_merged_ply(output_path, all_vertices)
    print("Merge complete!")

if __name__ == '__main__':
    try:
        main()
    except ImportError as e:
        if 'sklearn' in str(e):
            print("Error: scikit-learn required for deduplication")
            print("Install with: pip install scikit-learn")
            print("Or run without --deduplicate flag")
        else:
            raise

