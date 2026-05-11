#!/bin/bash -l
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=5
#SBATCH --time=1:00:00
#SBATCH --output=./logs/%j.out
#SBATCH --error=./logs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

# Load glomap environment and 
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

cd "$scripts_dir"

sparse_dir="$PROJECT_DIR/sparse_merged"


model_path="${sparse_dir}/cross_ABC"

if [ -n "$model_path" ]; then
    echo "Merged sparse model is $model_path."
fi


# Convert sparse .bin files to .txt
echo "running sparse conversion on ${model_path}"
colmap model_converter --input_path ${model_path} --output_path ${model_path} --output_type TXT

# Run chunking strategy and divide images
python chunking_strategy.py --sparse_dir ${model_path} --dense_dir "${PROJECT_DIR}/dense" \
    --spatial_overlap_distance ${dense_spat_overlap} --output_base "${PROJECT_DIR}/chunks" --num_chunks ${dense_chunk_num} --copy_files \
    --create_workspaces --strategy spatial --max_chunk_size 3000

echo "Prepared ${dense_chunk_num} chunks for ${trial_name} dense reconstruction."