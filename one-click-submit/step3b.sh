#!/bin/bash -l
#SBATCH --partition=aa100
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=21
#SBATCH --time=3:00:00
#SBATCH --output=./logs/%j.out
#SBATCH --error=./logs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

module purge
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env
echo "glomap mamba environment activated"

CHUNK_ID_PADDED=$(printf "%02d" "${CHUNK_IDX}")

echo "Running chunk ${CHUNK_IDX}"

echo "Processing Chunk ID: ${CHUNK_IDX} (Formatted as: ${CHUNK_ID_PADDED})"

CHUNK_DIR="${PROJECT_DIR}/chunks/chunk_${CHUNK_ID_PADDED}/dense"

# Check if chunk directory exists
if [ ! -d $CHUNK_DIR ]; then
    echo "ERROR: Chunk directory does not exist: \${CHUNK_DIR}"
    echo "Please run chunking_strategy.py with --create_workspaces first"
    #exit 1
fi

cd "${CHUNK_DIR}"

# Step 1: Run image undistorter to create workspace structure and config files
# This is REQUIRED - it creates stereo/patch-match.cfg and stereo/fusion.cfg
# Note: We use 'colmap' command (not 'glomap') because GLOMAP is only for sparse reconstruction.
# For dense reconstruction (image_undistorter, patch_match_stereo, stereo_fusion), we use COLMAP.
echo "Running image undistorter for chunk ${CHUNK_IDX}..."
colmap image_undistorter \
  --image_path "./images" \
  --input_path ./sparse \
  --output_path . \
  --output_type COLMAP \
  --max_image_size=1500

echo "image undistorter complete for chunk ${CHUNK_IDX}"

colmap patch_match_stereo \
  --workspace_path . \
  --workspace_format COLMAP \
  --PatchMatchStereo.geom_consistency=false \
  --PatchMatchStereo.filter=true \
  --PatchMatchStereo.max_image_size=1500 \
  --PatchMatchStereo.window_step=2 \
  --PatchMatchStereo.num_iterations=3 \
  --PatchMatchStereo.num_samples=15 \
  --PatchMatchStereo.gpu_index=0
 

echo "patch match stereo complete for chunk ${CHUNK_IDX}"

colmap stereo_fusion \
  --workspace_path . \
  --workspace_format COLMAP \
  --input_type photometric \
  --StereoFusion.max_image_size=1500 \
  --output_path ./fused_chunk_${CHUNK_IDX}.ply

echo "stereo fusion complete for chunk ${CHUNK_IDX}"