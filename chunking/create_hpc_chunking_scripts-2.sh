#!/bin/bash

PROJECT_NAME="${1:-MM_3fps_7_clean/MM_3fps_7_spatial_0704}"
PROJECT_DIR="/scratch/alpine/elhe2720/colmap/improve_snorkel/${PROJECT_NAME}"
NUM_CHUNKS="${2:-6}"
CHUNKING_STRATEGY="${3:-spatial}"

echo "Creating HPC chunking scripts for ${PROJECT_NAME}"
echo "Number of chunks: ${NUM_CHUNKS}"
echo "Strategy: ${CHUNKING_STRATEGY}"
echo ""

OUTPUT_DIR="hpc_chunking_scripts"
mkdir -p "${OUTPUT_DIR}"

for CHUNK_ID in $(seq 0 $((NUM_CHUNKS - 1))); do
    CHUNK_SCRIPT="${OUTPUT_DIR}/dense_reconstruction_chunk_${CHUNK_ID}.sh"
    
    cat > "${CHUNK_SCRIPT}" << EOF
#!/bin/bash -l
#SBATCH --partition=aa100
#SBATCH --job-name=dense_chunk_${CHUNK_ID}_${PROJECT_NAME}
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --ntasks=42
#SBATCH --time=5:00:00
#SBATCH --output=log_chunk_${CHUNK_ID}_%j.out
#SBATCH --error=log_chunk_${CHUNK_ID}_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=elhe2720@colorado.edu
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

module purge

# Try to load miniforge module, fallback to direct conda if module not available
if module load miniforge 2>/dev/null; then
    echo "Loaded miniforge module"
else
    echo "miniforge module not found, trying direct conda path"
    # Try common conda installation paths
    if [ -f "\$HOME/.conda/etc/profile.d/conda.sh" ]; then
        source "\$HOME/.conda/etc/profile.d/conda.sh"
    elif [ -f "/curc/sw/miniforge/etc/profile.d/conda.sh" ]; then
        source "/curc/sw/miniforge/etc/profile.d/conda.sh"
    elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
        source "/opt/conda/etc/profile.d/conda.sh"
    else
        echo "ERROR: Could not find conda. Please check your conda installation."
        exit 1
    fi
fi

# If mamba is used, source it so mamba activate works (avoids "Run 'mamba init'" in batch)
for mamba_script in "\$HOME/.local/share/mamba/etc/profile.d/mamba.sh" "\$HOME/miniforge3/etc/profile.d/mamba.sh" "\$HOME/mambaforge/etc/profile.d/mamba.sh"; do
    if [ -f "\$mamba_script" ]; then
        source "\$mamba_script" 2>/dev/null
        break
    fi
done

# Try conda first, then mamba (in case env was created with mamba)
conda activate glomap_env 2>/dev/null || mamba activate glomap_env 2>/dev/null
if [ \$? -ne 0 ]; then
    echo "ERROR: Failed to activate glomap_env (tried conda and mamba)"
    echo "If you use mamba, run 'mamba init' and start a new shell, or use conda to activate."
    echo "Check env exists: conda env list  (or mamba env list)"
    exit 1
fi
echo "glomap conda environment activated"

CHUNK_DIR="${PROJECT_DIR}/chunks/chunk_$(printf "%02d" ${CHUNK_ID})/dense"

# Check if chunk directory exists
if [ ! -d "\${CHUNK_DIR}" ]; then
    echo "ERROR: Chunk directory does not exist: \${CHUNK_DIR}"
    echo "Please run chunking_strategy.py with --create_workspaces first"
    exit 1
fi

cd "\${CHUNK_DIR}"

# Step 1: Run image undistorter to create workspace structure and config files
# This is REQUIRED - it creates stereo/patch-match.cfg and stereo/fusion.cfg
# Note: We use 'colmap' command (not 'glomap') because GLOMAP is only for sparse reconstruction.
# For dense reconstruction (image_undistorter, patch_match_stereo, stereo_fusion), we use COLMAP.
echo "Running image undistorter for chunk ${CHUNK_ID}..."
colmap image_undistorter \\
  --image_path "./images" \\
  --input_path ./sparse \\
  --output_path . \\
  --output_type COLMAP \\
  --max_image_size=1500

echo "image undistorter complete for chunk ${CHUNK_ID}"

colmap patch_match_stereo \\
  --workspace_path . \\
  --workspace_format COLMAP \\
  --PatchMatchStereo.geom_consistency=false \\
  --PatchMatchStereo.filter=true \\
  --max_image_size=1500 \\
  --PatchMatchStereo.window_step=2 \\
  --PatchMatchStereo.num_iterations=3 \\
  --PatchMatchStereo.num_samples=15 \\
  --PatchMatchStereo.gpu_index=0,1
 

echo "patch match stereo complete for chunk ${CHUNK_ID}"

colmap stereo_fusion \\
  --workspace_path . \\
  --workspace_format COLMAP \\
  --input_type photometric \\
  --StereoFusion.max_image_size=1500 \\
  --output_path ./fused_chunk_${CHUNK_ID}.ply

echo "stereo fusion complete for chunk ${CHUNK_ID}"

EOF
    chmod +x "${CHUNK_SCRIPT}"
    echo "Created ${CHUNK_SCRIPT}"
done

MERGE_SCRIPT="${OUTPUT_DIR}/merge_chunks.sh"
cat > "${MERGE_SCRIPT}" << EOF
#!/bin/bash
#SBATCH --partition=amilan
#SBATCH --job-name=merge_chunks_${PROJECT_NAME}
#SBATCH --nodes=1
#SBATCH --ntasks=20
#SBATCH --time=1:00:00
#SBATCH --output=log_merge_%j.out
#SBATCH --error=log_merge_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=elhe2720@colorado.edu
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

module purge

# Try to load miniforge module, fallback to direct conda if module not available
if module load miniforge 2>/dev/null; then
    echo "Loaded miniforge module"
else
    echo "miniforge module not found, trying direct conda path"
    # Try common conda installation paths
    if [ -f "\$HOME/.conda/etc/profile.d/conda.sh" ]; then
        source "\$HOME/.conda/etc/profile.d/conda.sh"
    elif [ -f "/curc/sw/miniforge/etc/profile.d/conda.sh" ]; then
        source "/curc/sw/miniforge/etc/profile.d/conda.sh"
    elif [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
        source "/opt/conda/etc/profile.d/conda.sh"
    else
        echo "ERROR: Could not find conda. Please check your conda installation."
        exit 1
    fi
fi

# If mamba is used, source it so mamba activate works (avoids "Run 'mamba init'" in batch)
for mamba_script in "\$HOME/.local/share/mamba/etc/profile.d/mamba.sh" "\$HOME/miniforge3/etc/profile.d/mamba.sh" "\$HOME/mambaforge/etc/profile.d/mamba.sh"; do
    if [ -f "\$mamba_script" ]; then
        source "\$mamba_script" 2>/dev/null
        break
    fi
done

# Try conda first, then mamba (in case env was created with mamba)
conda activate glomap_env 2>/dev/null || mamba activate glomap_env 2>/dev/null
if [ \$? -ne 0 ]; then
    echo "ERROR: Failed to activate glomap_env (tried conda and mamba)"
    echo "If you use mamba, run 'mamba init' and start a new shell, or use conda to activate."
    echo "Check env exists: conda env list  (or mamba env list)"
    exit 1
fi
echo "glomap conda environment activated"

PROJECT_DIR="${PROJECT_DIR}"
MERGED_OUTPUT="\${PROJECT_DIR}/dense/fused_chunked_merged.ply"

echo "Merging chunked point clouds..."
python3 merge_chunked_ply.py \\
  --project_dir "\${PROJECT_DIR}" \\
  --num_chunks ${NUM_CHUNKS} \\
  --output "\${MERGED_OUTPUT}"

echo "Merge complete: \${MERGED_OUTPUT}"

EOF
chmod +x "${MERGE_SCRIPT}"
echo "Created ${MERGE_SCRIPT}"

SUBMIT_ALL="${OUTPUT_DIR}/submit_all_chunks.sh"
cat > "${SUBMIT_ALL}" << EOF
#!/bin/bash

PROJECT_NAME="${PROJECT_NAME}"
NUM_CHUNKS=${NUM_CHUNKS}

echo "Submitting ${NUM_CHUNKS} chunk jobs for \${PROJECT_NAME}"

for CHUNK_ID in \$(seq 0 \$((NUM_CHUNKS - 1))); do
    echo "Submitting chunk \${CHUNK_ID}..."
    sbatch dense_reconstruction_chunk_\${CHUNK_ID}.sh
done

echo ""
echo "All chunk jobs submitted. To submit merge job after chunks complete:"
echo "sbatch merge_chunks.sh"

EOF
chmod +x "${SUBMIT_ALL}"
echo "Created ${SUBMIT_ALL}"

echo ""
echo "Chunking scripts created in ${OUTPUT_DIR}/"
echo ""
echo "Next steps:"
echo "1. Run chunking_strategy.py to create chunk directories on HPC"
echo "2. Copy scripts to HPC cluster"
echo "3. Run submit_all_chunks.sh to launch parallel chunk processing"
echo "4. Run merge_chunks.sh after all chunks complete"
