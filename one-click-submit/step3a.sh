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


chunk_dir="${PROJECT_DIR}/chunks"
num_chunks=$(find "$chunk_dir" -maxdepth 1 -mindepth 1 -type d | wc -l)
echo "Prepared ${num_chunks} chunks for ${trial_name} dense reconstruction."

# Step 3b: SUBMIT CHUNKS
chunk_ids=""
for (( c=0; c<${num_chunks}; c++ )); do
    curr_jid=$(sbatch --job-name="${trial_name}_dense_chunk_${c}" --export=ALL,CHUNK_IDX=$c step3b.sh | awk '{print $4}')

    # Build list of Job ID's
    if [ -z "$chunk_ids" ]; then
        chunk_ids="$curr_jid"
    else
        chunk_ids="${chunk_ids}:${curr_jid}"
    fi
done

echo "Submitted ${num_chunks} chunks: Dependency list ($chunk_ids)"
                
# Step 4: Merge, AMC, MVT, and Dense Meshing
    #TODO: Make time flag dependent on if AMC will be run
if [[ "$run_MVT" == "True" || "$dense_mesh" == "True" ]]; then                
    jid4=$(sbatch --job-name="${trial_name}_step4" --dependency=afterok:$chunk_ids --mail-user="$email" step4.sh | awk '{print $4}')
    echo "Submitted step 4 (merging, MVT, and Meshing): $jid4"
else
    echo "Skipping dense merging/meshing and MVT. Set dense_mesh or run_MVT to True if this step is desired" 
fi

echo "For ${trial_name}, step 3 & step 4 jobs are: ${chunk_ids},${jid4}. Saving to jobids.txt"
echo $(date "+%Y-%m-%d %H:%M:%S") >> "${PROJECT_DIR}/jobids.txt"
echo "Part 3 Job IDs for ${trial_name}: ${chunk_ids},${jid4}" >> "${PROJECT_DIR}/jobids.txt"