#!/bin/bash -l
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=30
#SBATCH --output=./logs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./logs/%j.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

echo "STEP 2: Chunked Sparse Reconstruction (image_list)"

cd "$scripts_dir"

# Load glomap environment and 
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

#### Define and create paths ####
IMAGES_DIR="${PROJECT_DIR}/images"
CHUNK_LIST_DIR="${PROJECT_DIR}/image_lists"
SPARSE_CHUNK_DIR="${PROJECT_DIR}/sparse_chunks"
MERGED_DIR="${PROJECT_DIR}/sparse_merged"

mkdir -p "$CHUNK_LIST_DIR" "$SPARSE_CHUNK_DIR" "$MERGED_DIR"

#### User-configurable parameters to define chunks #####

CHUNK_SIZE=$sparse_chunk_size       # number of images per chunk
OVERLAP=$sparse_chunk_overlap          # overlap between chunks
MAX_PARALLEL=$sparse_max_parallel     # number of chunks to process simultaneously

#### Create image lists for running separate chunks ####

echo "Creating image lists..."

##### Create chunks #####

python - <<EOF
import os, math

img_dir = "${IMAGES_DIR}"
left_dir = os.path.join(img_dir, "left")
right_dir = os.path.join(img_dir, "right")

left_images = sorted(os.listdir(left_dir))
right_images = sorted(os.listdir(right_dir))

N = len(left_images)

chunk_size = int("${CHUNK_SIZE}")
overlap = int("${OVERLAP}")

step = chunk_size - overlap
num_chunks = math.ceil((N - overlap) / step)

def write_chunk(start, end, idx):
    path = os.path.join("${CHUNK_LIST_DIR}", f"chunk{idx}.txt")
    with open(path, "w") as f:
        for i in range(start, end):
            f.write(f"left/{left_images[i]}\\n")
            f.write(f"right/{right_images[i]}\\n")

for i in range(num_chunks):
    start = i * step
    end = min(start + chunk_size, N)
    write_chunk(start, end, i+1)

print(f"Created {num_chunks} chunks")
EOF




#### Sparse reconstruction in parallel ####
pids=()

for chunk_file in "${CHUNK_LIST_DIR}"/chunk*.txt; do
    i=$(basename "$chunk_file" | sed 's/chunk\([0-9]*\).txt/\1/')

    (
        echo "Running chunk $i"

        OUT_DIR="${SPARSE_CHUNK_DIR}/chunk${i}"
        mkdir -p "$OUT_DIR"

        python runCOLMAP.py \
            --project_dir="$PROJECT_DIR" \
            --folder_path_L="$frames_path_L" \
            --folder_path_R="$frames_path_R" \
            --vocab_tree_path="$vocab_tree_path" \
            --extracted_fps=$extracted_fps \
            --final_fps=$final_fps \
            --mode="$mode" \
            --no_rename_images \
            --no_run_feat_ext_match \
            --no_run_dense \
            --image_list_path="$chunk_file" \
            --output_sparse_dir="$OUT_DIR"

        if [ ! -d "${OUT_DIR}/0" ]; then
            echo "ERROR: Chunk $i failed"
            exit 1
        fi
    ) &

    pids+=($!)

    # limit parallel jobs
    if [ "${#pids[@]}" -ge "$MAX_PARALLEL" ]; then
        wait -n
    fi
done

wait
echo "All chunks finished sparse reconstructing"

##### Finding largest models for each chunk to use in merging ####

# Define function to find the largest sub-model per chunk
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

#### Collect best models for merging ####

echo "Identifying best model for each chunk..."
chunk_paths=()

for d in "${SPARSE_CHUNK_DIR}"/chunk*; do
    best=$(find_largest_model "$d")

    if [ -z "$best" ]; then
        echo "ERROR: No model found in $d"
        exit 1
    fi

    echo "Selected model: $best"
    chunk_paths+=("$best")
done

#### Merge models in looping function ####

echo "Merging models..."

current_model="${chunk_paths[0]}"

for ((i=1; i<${#chunk_paths[@]}; i++)); do
    next_model="${chunk_paths[$i]}"
    out_model="${MERGED_DIR}/merge_$i"

    mkdir -p "$out_model"

    echo "Merging model $i..."

    colmap model_merger \
        --input_path1 "$current_model" \
        --input_path2 "$next_model" \
        --output_path "$out_model"

    current_model="$out_model"
done

FINAL_MODEL="$current_model"

echo "Step 2 COMPLETE"
echo "Final model: $FINAL_BA"

#### OPTIONAL: Perform bundle adjustment following merging ####

#echo "Performing bundle adjustment..."

#FINAL_BA="${MERGED_DIR}/final_model_ba"
#mkdir -p "$FINAL_BA"

#colmap bundle_adjuster \
#    --input_path "$FINAL_MODEL" \
#    --output_path "$FINAL_BA"

