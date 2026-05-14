#!/bin/bash -l

#########################
# SLURM CONFIG
# Lightweight orchestrator: generates image lists, submits array + merge.
#########################

#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=00:05:00
#SBATCH --output=./logs/%j.out
#SBATCH --error=./logs/%j.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

set -e

echo "STEP 2 [SUBMIT]: Generating image lists and submitting job array"

cd "$scripts_dir"

module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

#########################
# PATHS
#########################
IMAGES_DIR="${PROJECT_DIR}/images"
CHUNK_LIST_DIR="${PROJECT_DIR}/image_lists"
SPARSE_CHUNK_DIR="${PROJECT_DIR}/sparse_chunks"
MERGED_DIR="${PROJECT_DIR}/sparse_merged"

echo "Images dir: ${IMAGES_DIR}; Chunk list dir: ${CHUNK_LIST_DIR}; Sparse chunk dir: ${SPARSE_CHUNK_DIR}; Merged dir: ${MERGED_DIR}"
mkdir -p "${CHUNK_LIST_DIR}" "${SPARSE_CHUNK_DIR}" "${MERGED_DIR}"

#########################
# USER PARAMETERS
#########################
CHUNK_SIZE=$sparse_chunk_size
OVERLAP=$sparse_chunk_overlap
BORROWED=100

#########################
# CREATE IMAGE LISTS
# Images are split into 3 interleaved sets (A=every 3rd from frame 1,
# B=every 3rd from frame 2, C=every 3rd from frame 3). Each set is
# chunked temporally with CHUNK_SIZE and OVERLAP. To enable cross-set
# merging, each chunk also includes BORROWED frames drawn evenly from
# the adjacent set (A borrows from B, C borrows from B, B borrows
# equally from A and C). These borrowed frames will be registered in
# both sets' models, providing tie points for the cross-set merge.
#########################
echo "Creating interleaved image lists (sets A, B, C)..."
 
NUM_CHUNKS=$(python - <<EOF
import os, math
 
img_dir = "${IMAGES_DIR}"
left_dir = os.path.join(img_dir, "left")
right_dir = os.path.join(img_dir, "right")
 
left_images  = sorted(os.listdir(left_dir))
right_images = sorted(os.listdir(right_dir))
 
N = len(left_images)
chunk_size = int("${CHUNK_SIZE}")
overlap    = int("${OVERLAP}")
borrowed   = int("${BORROWED}")
step       = chunk_size - overlap
chunk_list_dir = "${CHUNK_LIST_DIR}"
 
# Split into 3 interleaved sets (0-indexed)
set_A = list(range(0, N, 3))   # frames 1, 4, 7, ...
set_B = list(range(1, N, 3))   # frames 2, 5, 8, ...
set_C = list(range(2, N, 3))   # frames 3, 6, 9, ...
 
def make_chunks(frame_list, chunk_size, overlap):
    """Return list of (start, end) index pairs into frame_list."""
    step = chunk_size - overlap
    n = len(frame_list)
    chunks = []
    i = 0
    while i < n:
        end = min(i + chunk_size, n)
        chunks.append((i, end))
        if end == n:
            break
        i += step
    return chunks
 
def interleave_borrowed(base_indices, borrow_indices, n_borrow):
    """
    Distribute n_borrow frames from borrow_indices evenly throughout
    base_indices. Returns a sorted list of combined image indices.
    """
    if n_borrow == 0 or len(borrow_indices) == 0:
        return list(base_indices)
    # Pick evenly spaced frames from the borrow set
    borrow_count = min(n_borrow, len(borrow_indices))
    step = max(1, len(borrow_indices) // borrow_count)
    picked = borrow_indices[::step][:borrow_count]
    combined = sorted(set(list(base_indices) + list(picked)))
    return combined
 
def write_chunk(image_indices, left_images, right_images, path):
    with open(path, "w") as f:
        for idx in image_indices:
            f.write(f"left/{left_images[idx]}\n")
            f.write(f"right/{right_images[idx]}\n")
 
chunks_A = make_chunks(set_A, chunk_size, overlap)
chunks_B = make_chunks(set_B, chunk_size, overlap)
chunks_C = make_chunks(set_C, chunk_size, overlap)
 
total_chunks = 0
chunk_num = 1
 
# --- Set A chunks (borrow from B) ---
for ci, (s, e) in enumerate(chunks_A):
    base   = set_A[s:e]
    # Borrow from the corresponding temporal region of set B
    b_s = max(0, s - borrowed // 2)
    b_e = min(len(set_B), e + borrowed // 2)
    borrow = set_B[b_s:b_e]
    combined = interleave_borrowed(base, borrow, borrowed)
    path = os.path.join(chunk_list_dir, f"setA_chunk{ci+1:04d}.txt")
    write_chunk(combined, left_images, right_images, path)
    chunk_num += 1
 
# --- Set B chunks (borrow equally from A and C) ---
half_borrow = borrowed // 2
for ci, (s, e) in enumerate(chunks_B):
    base   = set_B[s:e]
    b_s = max(0, s - half_borrow // 2)
    b_e = min(len(set_A), e + half_borrow // 2)
    borrow_A = set_A[b_s:b_e]
    b_s = max(0, s - half_borrow // 2)
    b_e = min(len(set_C), e + half_borrow // 2)
    borrow_C = set_C[b_s:b_e]
    combined = interleave_borrowed(base, borrow_A + borrow_C, borrowed)
    path = os.path.join(chunk_list_dir, f"setB_chunk{ci+1:04d}.txt")
    write_chunk(combined, left_images, right_images, path)
    chunk_num += 1
 
# --- Set C chunks (borrow from B) ---
for ci, (s, e) in enumerate(chunks_C):
    base   = set_C[s:e]
    b_s = max(0, s - borrowed // 2)
    b_e = min(len(set_B), e + borrowed // 2)
    borrow = set_B[b_s:b_e]
    combined = interleave_borrowed(base, borrow, borrowed)
    path = os.path.join(chunk_list_dir, f"setC_chunk{ci+1:04d}.txt")
    write_chunk(combined, left_images, right_images, path)
    chunk_num += 1
 
total_chunks = len(chunks_A) + len(chunks_B) + len(chunks_C)
 
print(f"{total_chunks},{len(chunks_A)},{len(chunks_B)},{len(chunks_C)}")
EOF
)
 
# Parse output
TOTAL_CHUNKS=$(echo $NUM_CHUNKS | cut -d',' -f1)
N_A=$(echo $NUM_CHUNKS | cut -d',' -f2)
N_B=$(echo $NUM_CHUNKS | cut -d',' -f3)
N_C=$(echo $NUM_CHUNKS | cut -d',' -f4)
 
echo "Created ${TOTAL_CHUNKS} total chunks: Set A=${N_A}, Set B=${N_B}, Set C=${N_C}"
 
# Export set counts for merge script
export N_A N_B N_C
 
#########################
# SUBMIT JOB ARRAY
# Each task runs independently on its own node.
# The array index maps to chunk files via step2_chunk.sh which
# now reads setA_chunk, setB_chunk, setC_chunk files.
#########################
ARRAY_JID=$(sbatch \
    --job-name="${trial_name}_step2_chunks" \
    --array="1-${TOTAL_CHUNKS}" \
    --mail-user="$email" \
    --mail-type=FAIL \
    --export=ALL \
    step2_chunk.sh | awk '{print $4}')
 
echo "Submitted chunk array: job $ARRAY_JID, tasks 1–${TOTAL_CHUNKS}"
 
#########################
# SUBMIT MERGE (runs only after ALL array tasks succeed)
#########################
MERGE_JID=$(sbatch \
    --job-name="${trial_name}_step2_merge" \
    --dependency="afterok:${ARRAY_JID}" \
    --mail-user="$email" \
    --mail-type=ALL \
    --export=ALL \
    step2_merge.sh | awk '{print $4}')
 
echo "Submitted merge job: $MERGE_JID (depends on array $ARRAY_JID)"
 
echo ""
echo "To monitor:"
echo "  squeue --job ${ARRAY_JID}      # watch array tasks"
echo "  squeue --job ${MERGE_JID}      # watch merge job"
echo "  squeue -u \$USER               # all your jobs"

#### SUBMIT STEPS 3 and 4 #### 

if [[ "$run_dense" == "True" ]]; then
                
    # Step 3a: PREP (Conversion & Chunking) 
    jid3_prep=$(sbatch --job-name="${trial_name}_prep" --dependency=afterok:$MERGE_JID --mail-user="$email" step3a.sh | awk '{print $4}')
    echo "Submitted Step 3 Prep (dense chunking): $jid3_prep"
    
    echo $(date "+%Y-%m-%d %H:%M:%S") >> "${PROJECT_DIR}/jobids.txt"
    echo "Part 2 Job IDs for ${trial_name}: ${ARRAY_JID}, ${MERGE_JID},${jid3_prep}" >> "${PROJECT_DIR}/jobids.txt"
else
    echo "Skipping Dense Reconstruction. Set run_dense=True in configs.sh if this step is desired" 
fi