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

#########################
# CREATE IMAGE LISTS
#########################
echo "Creating image lists..."

NUM_CHUNKS=$(python - <<EOF
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

chunk_list_dir = "${CHUNK_LIST_DIR}"

def write_chunk(start, end, idx):
    path = os.path.join(chunk_list_dir, f"chunk{idx:04d}.txt")
    with open(path, "w") as f:
        for i in range(start, end):
            f.write(f"left/{left_images[i]}\n")
            f.write(f"right/{right_images[i]}\n")

for i in range(num_chunks):
    start = i * step
    end = min(start + chunk_size, N)
    write_chunk(start, end, i + 1)

print(num_chunks)
EOF
)

echo "Created $NUM_CHUNKS chunks (indices 1–$NUM_CHUNKS)"

#########################
# SUBMIT JOB ARRAY
# Each chunk will run independently on its own node with 12 CPU
#########################
ARRAY_JID=$(sbatch \
    --job-name="${trial_name}_step2_chunks" \
    --array="1-${NUM_CHUNKS}" \
    --mail-user="${email}" \
    --mail-type=FAIL \
    --export=ALL \
    step2_chunk.sh | awk '{print $4}')

echo "Submitted chunk array: job $ARRAY_JID, tasks 1–${NUM_CHUNKS}"


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

# Write merge JID to file so submit_full_pipeline.sh can chain step3 correctly
echo "$MERGE_JID" > "${PROJECT_DIR}/merge_jid.txt"

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

    # Step 3b: SUBMIT CHUNKS
    chunk_ids=""
    for (( c=0; c<${dense_chunk_num}; c++ )); do
        curr_jid=$(sbatch --job-name="${trial_name}_dense_chunk_${c}" --dependency=afterok:$jid3_prep --export=ALL,CHUNK_IDX=$c step3b.sh | awk '{print $4}')

        # Build list of Job ID's
        if [ -z "$chunk_ids" ]; then
            chunk_ids="$curr_jid"
        else
            chunk_ids="${chunk_ids}:${curr_jid}"
        fi
    done

    echo "Submitted ${dense_chunk_num} chunks: Dependency list ($chunk_ids)"
                
    # Step 4: Merge, AMC, MVT, and Dense Meshing
    #TODO: Make time flag dependent on if AMC will be run
                
    jid4=$(sbatch --job-name="${trial_name}_step4" --dependency=afterok:$chunk_ids --mail-user="$email" step4.sh | awk '{print $4}')
    echo "Submitted step 4 (merging, MVT, and Meshing): $jid4"
    echo "For ${trial_name}, jobs are: ${jid3_prep},${chunk_ids},${jid4}. Saved to jobids.txt"
    echo "Part 2 Job IDs for ${trial_name}: ${MERGE_JID},${jid3_prep},${chunk_ids},${jid4}" >> "${PROJECT_DIR}/jobids.txt"
else
    echo "Skipping Dense Reconstruction. Set run_dense=True in configs.sh if this step is desired" 
fi
