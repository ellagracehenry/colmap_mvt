#!/bin/bash -l

#########################
# SLURM CONFIG
# Submitted as a job array by step2_submit.sh.
# Each task runs on its own node with 16 CPUs.
# Do not submit this directly.
#########################
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --time=16:00:00
#SBATCH --output=./logs/%A_%a.out
#SBATCH --error=./logs/%A_%a.err
#SBATCH --mail-user="${email}"
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

set -e

echo "STEP 2 [ARRAY CHUNK ${SLURM_ARRAY_TASK_ID}]: node=$(hostname) cpus=${SLURM_NTASKS}"

cd "$scripts_dir"

module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

#########################
# PATHS
#########################
CHUNK_LIST_DIR="${PROJECT_DIR}/image_lists"
SPARSE_CHUNK_DIR="${PROJECT_DIR}/sparse_chunks"

TASK_ID=${SLURM_ARRAY_TASK_ID}

if [ "$TASK_ID" -le "$N_A" ]; then
    SET_NAME="setA"
    SET_IDX=$TASK_ID
elif [ "$TASK_ID" -le "$((N_A + N_B))" ]; then
    SET_NAME="setB"
    SET_IDX=$((TASK_ID - N_A))
else
    SET_NAME="setC"
    SET_IDX=$((TASK_ID - N_A - N_B))
fi

CHUNK_INDEX=$(printf '%04d' "${SET_IDX}")
CHUNK_FILE="${CHUNK_LIST_DIR}/${SET_NAME}_chunk${CHUNK_INDEX}.txt"
OUT_DIR="${SPARSE_CHUNK_DIR}/${SET_NAME}_chunk${CHUNK_INDEX}"

mkdir -p "$OUT_DIR"

if [ ! -f "$CHUNK_FILE" ]; then
    echo "ERROR: Chunk file not found: $CHUNK_FILE"
    exit 1
fi

echo "Chunk file:  $CHUNK_FILE"
echo "Output dir:  $OUT_DIR"
echo "Local scratch: $SLURM_SCRATCH"

#########################
# STAGE INPUTS TO LOCAL SCRATCH
# $SLURM_SCRATCH is local NVMe SSD on the compute node — no network,
# no contention with other array tasks hitting the Lustre filesystem.
# Per CURC best practices, copying shared data here before I/O-heavy
# work is the highest-performance option available.
# Files in $SLURM_SCRATCH are deleted automatically when the job ends.
#########################
LOCAL_DIR="${SLURM_SCRATCH}/${SET_NAME}_chunk${CHUNK_INDEX}"
mkdir -p "${LOCAL_DIR}"

echo "Staging database to local scratch..."
cp "${PROJECT_DIR}/database.db" "${LOCAL_DIR}/database.db"

echo "Staging images to local scratch..."
rsync -a "${PROJECT_DIR}/images/" "${LOCAL_DIR}/images/"

echo "Staging complete."

#########################
# RUN COLMAP
# --project_dir points at LOCAL_DIR so database.db and images/ are
# read from local NVMe rather than Lustre scratch.
# --output_sparse_dir also writes to LOCAL_DIR to keep all I/O local.
# The final model is copied back to OUT_DIR on Lustre after completion.
#########################
python runCOLMAP.py \
    --project_dir="${LOCAL_DIR}" \
    --folder_path_L="$frames_path_L" \
    --folder_path_R="$frames_path_R" \
    --vocab_tree_path="$vocab_tree_path" \
    --extracted_fps=$extracted_fps \
    --final_fps=$final_fps \
    --no_rename_images \
    --no_run_feat_ext_match \
    --no_run_dense \
    --image_list_path="$CHUNK_FILE" \
    --output_sparse_dir="${LOCAL_DIR}/sparse"

#########################
# COPY OUTPUT BACK TO LUSTRE
# Must happen before job ends — $SLURM_SCRATCH is wiped on completion.
# Only copy the sparse model, not the database or images.
#########################
if [ ! -d "${LOCAL_DIR}/sparse/0" ]; then
    echo "ERROR: Chunk ${SLURM_ARRAY_TASK_ID} failed — no model in ${LOCAL_DIR}/sparse"
    exit 1
fi

echo "Copying sparse model output back to project dir..."
cp -r "${LOCAL_DIR}/sparse/." "${OUT_DIR}/"

echo "Chunk ${SLURM_ARRAY_TASK_ID} complete. Model at: ${OUT_DIR}"