#!/usr/bin/env python3

import argparse
import struct
from pathlib import Path


def read_ply_header(file_path):
    with open(file_path, 'rb') as f:
        header_lines = []
        while True:
            line = f.readline()
            header_lines.append(line)
            if b'end_header' in line:
                break
        return b''.join(header_lines), f.tell()


def read_ply_vertices(file_path, vox_size):
    header, data_start = read_ply_header(file_path)

    num_vertices = None
    for line in header.split(b'\n'):
        if b'element vertex' in line:
            num_vertices = int(line.split()[-1])
            break

    if num_vertices is None:
        raise ValueError("Could not find vertex count in PLY header")

    seen = set()
    inv = 1.0 / vox_size

    with open(file_path, 'rb') as f:
        f.seek(data_start)
        for _ in range(num_vertices):
            raw = f.read(27)
            if len(raw) < 27:
                break
            x, y, z = struct.unpack_from('<fff', raw, 0)
            key = (int(x * inv), int(y * inv), int(z * inv))
            if key not in seen:
                seen.add(key)
                yield raw


def write_merged_ply(output_path, all_vertices):
    header_template = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "element vertex {vertex_count}\n"
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

    placeholder = header_template.format(vertex_count="0" * 12).encode('ascii')
    total = 0

    with open(output_path, 'wb') as f:
        f.write(placeholder)
        for raw in all_vertices:
            f.write(raw)
            total += 1

            if total % 1_000_000 == 0:
                print(f"  Written {total:,} vertices...")

    correct = header_template.format(vertex_count=str(total).ljust(12)).encode('ascii')
    with open(output_path, 'r+b') as f:
        f.write(correct)

    print(f"Merged {total:,} vertices into {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Merge chunked PLY point clouds')
    parser.add_argument('--project_dir', type=str, required=True, help='Project directory containing chunks')
    parser.add_argument('--num_chunks', type=int, required=True, help='Number of chunks to merge')
    parser.add_argument('--output', type=str, required=True, help='Output PLY file path')
    parser.add_argument('--vox_size', type=float, default=0.005, help='Size of voxel to de-duplicate over')

    parser.add_argument('--deduplicate', action='store_true', help='Remove duplicate points (within 1mm)')

    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vox_size=float(args.vox_size)

    print(f"Reading {args.num_chunks} chunk files...")

    def all_vertices():
        for chunk_id in range(args.num_chunks):
            chunk_file = project_dir / "chunks" / f"chunk_{chunk_id:02d}" / "dense" / f"fused_chunk_{chunk_id}.ply"
            if not chunk_file.exists():
                print(f"Warning: {chunk_file} not found, skipping")
                continue
            print(f"Reading chunk {chunk_id}: {chunk_file}")
            yield from read_ply_vertices(chunk_file, vox_size)

    print(f"\nWriting new non-OOM merged PLY to {output_path}...")
    write_merged_ply(output_path, all_vertices())
    print("Merge complete!")


if __name__ == '__main__':
    main()