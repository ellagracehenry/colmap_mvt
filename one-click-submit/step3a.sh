#!/bin/bash -l
#SBATCH --partition=aa100
#SBATCH --nodes=1
#SBATCH --ntasks=10
#SBATCH --gres=gpu:1
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

model_path="${sparse_dir}/cross_ABC_ba"

if [ -n "$model_path" ]; then
    echo "Merged sparse model is $model_path."
fi

# Undistort images
colmap image_undistorter \
  --image_path "${PROJECT_DIR}/images" \
  --input_path "${model_path}" \
  --output_path "${PROJECT_DIR}/dense" \
  --output_type COLMAP \
  --max_image_size=1500


#Step 2: Split up the patch_match.cfg file to chunk patch match
cd ${PROJECT_DIR}/dense/stereo
split -l 2000 patch-match.cfg chunk_cfg_


chunk_dir="${PROJECT_DIR}/chunks"
cd "$scripts_dir"

# Submit Step 3.b: Patch-match in stereo: 
chunk_ids=""
for chunk_file in "${PROJECT_DIR}/dense/stereo"/chunk_cfg_*; do   
    [[ -e "$chunk_file" ]] || continue;  
    echo "Submitting $chunk_file" ;
    curr_jid=$(sbatch --export=ALL,chunk_file="$(basename "$chunk_file")" --job-name="${trial_name}_pm_$(basename "$chunk_file")" --mail-user="$email" step3b.sh | awk '{print $4}')
        # Build list of Job ID's
    if [ -z "$chunk_ids" ]; then
        chunk_ids="$curr_jid"
    else
        chunk_ids="${chunk_ids}:${curr_jid}"
    fi
done


echo "Submitted dense chunks for patch-match: Dependency list ($chunk_ids)"

# Submit Step 3.c: Dense fusion
jid3c=$(sbatch --job-name="${trial_name}_fusion" --dependency=afterok:$chunk_ids --mail-user="$email" step3c.sh | awk '{print $4}')
echo "submitted dense fusion for patch-match: $jid3c"
                
# Step 4: Merge, AMC, MVT, and Dense Meshing
    #TODO: Make time flag dependent on if AMC will be run
if [[ "$run_MVT" == "True" || "$dense_mesh" == "True" ]]; then                
    jid4=$(sbatch --job-name="${trial_name}_step4" --dependency=afterok:$jid3c --mail-user="$email" step4.sh | awk '{print $4}')
    echo "Submitted step 4 (merging, MVT, and Meshing): $jid4"
else
    echo "Skipping dense merging/meshing and MVT. Set dense_mesh or run_MVT to True if this step is desired" 
fi

echo "For ${trial_name}, step 3 & step 4 jobs are: ${chunk_ids},${jid3c}, ${jid4}. Saving to jobids.txt"
echo $(date "+%Y-%m-%d %H:%M:%S") >> "${PROJECT_DIR}/jobids.txt"
echo "Part 3 Job IDs for ${trial_name}: ${chunk_ids},${jid3c},${jid4}" >> "${PROJECT_DIR}/jobids.txt"