#!/bin/bash -l

#########################
# SLURM CONFIG
# Submitted by step2_submit.sh with --dependency=afterok:<array_job_id>
#########################
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=5
#SBATCH --time=01:00:00
#SBATCH --output=./logs/%j_merge.out
#SBATCH --error=./logs/%j_merge.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

set -e

echo "STEP 2 [MERGE]: Within-set merge then cross-set merge"

cd "$scripts_dir"

module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

#########################
# PATHS
#########################
SPARSE_CHUNK_DIR="${PROJECT_DIR}/sparse_chunks"
MERGED_DIR="${PROJECT_DIR}/sparse_merged"

mkdir -p "$MERGED_DIR" # remove if it already exists

#########################
# PYTHON HELPERS
# Shared functions for reading images.bin and reporting overlap.
# Used throughout the merge steps below.
#########################
read_names_py='
import struct, sys

def read_image_names(path):
    names = set()
    try:
        with open(path, "rb") as f:
            num_images = struct.unpack("<Q", f.read(8))[0]
            for _ in range(num_images):
                struct.unpack("<I", f.read(4))
                f.read(32)
                f.read(24)
                struct.unpack("<I", f.read(4))
                name = b""
                while True:
                    c = f.read(1)
                    if c == b"\x00":
                        break
                    name += c
                names.add(name.decode("utf-8"))
                num_points2D = struct.unpack("<Q", f.read(8))[0]
                f.read(num_points2D * 24)
    except Exception as e:
        print(f"WARNING: could not read {path}: {e}", file=sys.stderr)
    return names
'

#########################
# SUBMODEL SELECTION
# For each set, select the best submodel per chunk using the
# overlap-based forward pass strategy:
#   - First chunk: largest images.bin
#   - Subsequent chunks: most shared images with previous selection
#########################
echo "============================================================"
echo "Selecting best submodels for each set..."

select_submodels() {
    local set_name=$1
    local n_chunks=$2
    local out_file=$3

    python3 - <<PYEOF
$read_names_py
import os, sys, struct

sparse_chunk_dir = "${SPARSE_CHUNK_DIR}"
set_name = "$set_name"
n_chunks = int("$n_chunks")
out_file = "$out_file"

selected = []
prev_names = None

for ci in range(1, n_chunks + 1):
    chunk_dir = os.path.join(sparse_chunk_dir, f"{set_name}_chunk{ci:04d}")
    if not os.path.isdir(chunk_dir):
        print(f"ERROR: {chunk_dir} not found", file=sys.stderr)
        sys.exit(1)

    submodels = sorted([
        os.path.join(chunk_dir, s)
        for s in os.listdir(chunk_dir)
        if os.path.isdir(os.path.join(chunk_dir, s))
    ])

    if not submodels:
        print(f"ERROR: No submodels in {chunk_dir}", file=sys.stderr)
        sys.exit(1)

    if prev_names is None:
        # First chunk — pick largest images.bin
        best = max(submodels,
                   key=lambda d: os.path.getsize(os.path.join(d, "images.bin"))
                   if os.path.exists(os.path.join(d, "images.bin")) else 0)
        names = read_image_names(os.path.join(best, "images.bin"))
        print(f"{set_name} chunk {ci:04d}: selected {os.path.basename(best)} (largest images.bin — first chunk)")
    else:
        best = None
        best_overlap = -1
        names = set()
        for sub in submodels:
            img_bin = os.path.join(sub, "images.bin")
            if not os.path.exists(img_bin):
                continue
            n = read_image_names(img_bin)
            overlap = len(n & prev_names)
            if overlap > best_overlap:
                best_overlap = overlap
                best = sub
                names = n
        print(f"{set_name} chunk {ci:04d}: selected {os.path.basename(best)} ({best_overlap} shared with previous)")

    prev_names = names
    selected.append(best)

with open(out_file, "w") as f:
    for p in selected:
        f.write(p + "\n")
PYEOF
}

SEL_A="${MERGED_DIR}/selected_setA.txt"
SEL_B="${MERGED_DIR}/selected_setB.txt"
SEL_C="${MERGED_DIR}/selected_setC.txt"

select_submodels "setA" "$N_A" "$SEL_A"
select_submodels "setB" "$N_B" "$SEL_B"
select_submodels "setC" "$N_C" "$SEL_C"

#########################
# WITHIN-SET SEQUENTIAL MERGE FUNCTION
# Merges chunks within a single set sequentially, reporting shared
# images at each step and flagging zero-overlap transitions.
#########################
merge_set() {
    local set_name=$1
    local sel_file=$2
    local out_prefix=$3

    echo "------------------------------------------------------------" >&2
    echo "Merging within $set_name..." >&2

    mapfile -t paths < "$sel_file"

    if [ ${#paths[@]} -eq 0 ]; then
        echo "ERROR: No selected models for $set_name" >&2
        exit 1
    fi

    local current="${paths[0]}"
    local broken=()

    for ((i=1; i<${#paths[@]}; i++)); do
        local next="${paths[$i]}"
        local out="${out_prefix}_$(printf '%04d' $i)"
        mkdir -p "$out"

        local shared
        shared=$(python3 - <<PYEOF
$read_names_py
a = read_image_names("${current}/images.bin")
b = read_image_names("${next}/images.bin")
print(len(a & b))
PYEOF
)
        echo "  Step $i: $(basename $current) + $(basename $next) — shared: $shared" >&2

        if [ "$shared" -eq 0 ]; then
            echo "  *** WARNING: ZERO shared images at $set_name step $i ***" >&2
            broken+=("$i")
        fi

        colmap model_merger \
            --input_path1 "$current" \
            --input_path2 "$next" \
            --output_path "$out"

        current="$out"
    done

    if [ ${#broken[@]} -gt 0 ]; then
        echo "  *** WARNING: $set_name had ${#broken[@]} zero-overlap step(s): ${broken[*]} ***" >&2
    else
        echo "  $set_name within-set merge complete — all steps had shared images." >&2
    fi

    echo "$current"
}

#########################
# WITHIN-SET MERGES
#########################
echo "============================================================"
echo "PHASE 1: Within-set merges"

MODEL_A=$(merge_set "setA" "$SEL_A" "${MERGED_DIR}/setA_merge")
MODEL_B=$(merge_set "setB" "$SEL_B" "${MERGED_DIR}/setB_merge")
MODEL_C=$(merge_set "setC" "$SEL_C" "${MERGED_DIR}/setC_merge")

echo ""
echo "Within-set merge results:"
echo "  Model A: $MODEL_A"
echo "  Model B: $MODEL_B"
echo "  Model C: $MODEL_C"

#########################
# CROSS-SET MERGE
# Merge order: A + B → AB, then AB + C → final
# Report shared images at each cross-set step — zero overlap here
# means the borrowed frame strategy did not produce enough tie points
# and the affected set should be rerun.
#########################
echo "============================================================"
echo "PHASE 2: Cross-set merges"

cross_merge() {
    local label=$1
    local model1=$2
    local model2=$3
    local out=$4

    rm -rf "$out"
    mkdir -p "$out"

    local shared
    shared=$(python3 - <<PYEOF
$read_names_py
a = read_image_names("${model1}/images.bin")
b = read_image_names("${model2}/images.bin")
print(len(a & b))
PYEOF
)
    echo "  $label: shared images = $shared" >&2

    if [ "$shared" -eq 0 ]; then
        echo "  *** WARNING: ZERO shared images for $label — cross-set merge will produce a disconnected model ***" >&2
        echo "  *** Consider rerunning affected chunks with increased BORROWED frame count ***" >&2
    fi

    colmap model_merger \
        --input_path1 "$model1" \
        --input_path2 "$model2" \
        --output_path "$out"

    echo "$out"
}

MODEL_AB=$(cross_merge "A + B" "$MODEL_A" "$MODEL_B" "${MERGED_DIR}/cross_AB")
FINAL_MODEL=$(cross_merge "AB + C" "$MODEL_AB" "$MODEL_C" "${MERGED_DIR}/cross_ABC")

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
echo "============================================================"
echo "Step 2 [MERGE ALT] COMPLETE"
echo "Final model: $FINAL_MODEL"