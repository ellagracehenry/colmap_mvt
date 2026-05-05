#!/bin/bash -l

#########################
# SLURM CONFIG
# Submitted by step2_submit.sh with --dependency=afterok:<array_job_id>
#########################
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=00:10:00
#SBATCH --output=./logs/%j_merge.out
#SBATCH --error=./logs/%j_merge.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

set -e

echo "STEP 2 [MERGE]: Combining chunk models"

cd "$scripts_dir"

module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

#########################
# PATHS
#########################
SPARSE_CHUNK_DIR="${PROJECT_DIR}/sparse_chunks"
MERGED_DIR="${PROJECT_DIR}/sparse_merged"

mkdir -p "$MERGED_DIR"

#########################
# FIND BEST MODEL PER CHUNK
#########################
echo "Selecting best model per chunk..."

find_largest_model() {
    local chunk_dir=$1
    local best_path=""
    local best_size=0

    for d in "$chunk_dir"/*/; do
        [ -d "$d" ] || continue
        img_file="${d}images.bin"
        if [ -f "$img_file" ]; then
            size=$(stat -c%s "$img_file")
            if [ "$size" -gt "$best_size" ]; then
                best_size=$size
                best_path="$d"
            fi
        fi
    done

    echo "$best_path"
}

chunk_paths=()

# Sort numerically so merge order matches temporal order
for d in $(ls -d "${SPARSE_CHUNK_DIR}"/chunk* | sort -V); do
    best=$(find_largest_model "$d")
    if [ -z "$best" ]; then
        echo "ERROR: No model found in $d"
        exit 1
    fi
    echo "Selected: $best"
    chunk_paths+=("$best")
done

echo "Merging ${#chunk_paths[@]} models..."

#########################
# SEQUENTIAL MERGE
# Before each merge, shared images between the current and next model
# are reported. If zero overlap is detected, a WARNING flag is printed
# and the merge step is recorded — the merge will still run but will
# likely produce a disconnected model at that point.
#########################
current_model="${chunk_paths[0]}"
broken_merges=()

for ((i=1; i<${#chunk_paths[@]}; i++)); do
    next_model="${chunk_paths[$i]}"
    out_model="${MERGED_DIR}/merge_$(printf '%04d' $i)"
    mkdir -p "$out_model"

    # Count shared images between current and next model before merging
    shared=$(python3 - <<PYEOF
import struct

def read_image_names(path):
    names = set()
    try:
        with open(path, 'rb') as f:
            num_images = struct.unpack('<Q', f.read(8))[0]
            for _ in range(num_images):
                struct.unpack('<I', f.read(4))
                f.read(32)
                f.read(24)
                struct.unpack('<I', f.read(4))
                name = b''
                while True:
                    c = f.read(1)
                    if c == b'\x00':
                        break
                    name += c
                names.add(name.decode('utf-8'))
                num_points2D = struct.unpack('<Q', f.read(8))[0]
                f.read(num_points2D * 24)
    except:
        pass
    return names

current_names = read_image_names("${current_model}/images.bin")
next_names = read_image_names("${next_model}/images.bin")
print(len(current_names & next_names))
PYEOF
)

    echo "------------------------------------------------------------"
    echo "Merge step $i: $(basename $current_model) + $(basename $next_model)"
    echo "  Shared images: $shared"

    if [ "$shared" -eq 0 ]; then
        echo "  *** WARNING: ZERO shared images — merge step $i will produce a disconnected model ***"
        echo "  *** Consider rerunning the chunk that produced: $(basename $next_model) ***"
        broken_merges+=("$i")
    fi

    colmap model_merger \
        --input_path1 "$current_model" \
        --input_path2 "$next_model" \
        --output_path "$out_model"

    current_model="$out_model"
done

FINAL_MODEL="$current_model"

# Print summary of any broken merge steps
if [ ${#broken_merges[@]} -gt 0 ]; then
    echo "============================================================"
    echo "*** WARNING: ${#broken_merges[@]} merge step(s) had ZERO shared images ***"
    echo "*** Broken merge steps: ${broken_merges[*]} ***"
    echo "*** The final model may be disconnected at these points  ***"
    echo "*** Rerun the affected chunks before dense reconstruction ***"
    echo "============================================================"
    exit 1
else
    echo "All merge steps had shared images — model sequence is intact."
fi

#########################
# OPTIONAL BUNDLE ADJUSTMENT
#########################
# Uncomment to enable:
# FINAL_BA="${MERGED_DIR}/final_model_ba"
# mkdir -p "$FINAL_BA"
# colmap bundle_adjuster \
#     --input_path "$FINAL_MODEL" \
#     --output_path "$FINAL_BA"
# FINAL_MODEL="$FINAL_BA"

#########################
# DONE
#########################
echo "Step 2 [MERGE] COMPLETE"
echo "Final model: $FINAL_MODEL"