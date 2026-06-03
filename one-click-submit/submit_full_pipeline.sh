#!/bin/bash -l
set -e

# Read from configs
source configs.sh

# First, check that the correct lengths of essential config values are provided
arrays_to_check=(
  frames_paths_L
  frames_paths_R
)
expected_len=${#trial_names[@]}

for arr_name in "${arrays_to_check[@]}"; do
    # indirect expansion to get array length dynamically
    arr_len=$(eval "echo \${#${arr_name}[@]}")

    if [[ "$arr_len" -ne "$expected_len" ]]; then
        echo "Length mismatch:"
        echo "  trial_names     = $expected_len"
        echo "  $arr_name = $arr_len"
        exit 1
    fi
done


for i in "${!trial_names[@]}"; do
    trial_name=${trial_names[$i]}
    frames_path_L=${frames_paths_L[$i]}
    frames_path_R=${frames_paths_R[$i]}
    mask_path_L=${masks_paths_L[$i]}
    mask_path_R=${masks_paths_R[$i]}
    observation_id_L=${observation_ids_L[$i]}
    observation_id_R=${observation_ids_R[$i]}
    annotations_L=${annotations_paths_L[$i]}
    annotations_R=${annotations_paths_R[$i]}
    world_distance=${world_distances[$i]}
    extracted_fps=${extracted_fpss[$i]}
    final_fps=${final_fpss[$i]}
    
    
    echo "======================================"
    echo "Submitting trial: $trial_name"
    echo "======================================"
    PROJECT_DIR="${ROOT_DIR}/${trial_name}" 
    if [ ! -d "${PROJECT_DIR}" ]; then
        mkdir "${PROJECT_DIR}"
    fi
    
    base_name="configs_used"
    ext=".sh"
    dest_file="${PROJECT_DIR}/${base_name}${ext}"
    
    # If the file exists, find the next available numbered version
    if [[ -e "$dest_file" ]]; then
        i=1
        while [[ -e "${PROJECT_DIR}/${base_name}_${i}${ext}" ]]; do
            ((i++))
        done
        dest_file="${PROJECT_DIR}/${base_name}_${i}${ext}"
    fi
    cp configs.sh "$dest_file"
    
    export trial_name frames_path_L frames_path_R mask_path_L mask_path_R observation_id_L observation_id_R PROJECT_DIR \
      annotations_L annotations_R world_distance ROOT_DIR scripts_dir vocab_tree_path extracted_fps final_fps  email \
      rename_images run_feat_ext_match run_sparse run_dense interpolate_points extract_centroids run_MMC run_AMC run_MVT err_threshold errors_csv_path \
      sparse_chunk_size sparse_chunk_overlap dense_chunk_num dense_spat_overlap dense_mesh


    
    if [[ "$rename_images" == "True" || "$run_feat_ext_match" == "True" ]]; then
        jid1=$(sbatch --job-name="${trial_name}_step1" --mail-user="$email" --mail-type=ALL step1.sh | awk '{print $4}')
        echo "Submitted step1 (Image organization and feature matching): $jid1"
        
        if [[ "$run_sparse" == "True" ]]; then
                jid2=$(sbatch --job-name="${trial_name}_step2" --dependency=afterok:$jid1 --mail-user="$email" --mail-type=ALL step2_submit.sh | awk '{print $4}')
                echo "Submitted step2: Sparse Reconstruction (COLMAP) with chunking: $jid2"
        fi
        if [[ "$run_dense" == "True" ]]; then
            echo "Dense cloud reconstruction and MVT (steps 3 & 4) will be automatically submitted after sparse reconstruction"
        fi
    else
        if [[ "$run_sparse" == "True" ]]; then
            jid2=$(sbatch --job-name="${trial_name}_step2" --mail-user="$email" --mail-type=ALL step2_submit.sh | awk '{print $4}')
            echo "Submitted step2: Sparse Reconstruction (COLMAP) with chunking: $jid2"
            
            if [[ "$run_dense" == "True" ]]; then
                echo "Dense cloud reconstruction and MVT (steps 3 & 4) will be automatically submitted after sparse reconstruction"
            fi    
            
        # Queue Step 3 here if already done with sparse reconstruction
        else
            if [[ "$run_dense" == "True" ]]; then
                
                # Step 3a: PREP (Conversion & Chunking) 
                jid3_prep=$(sbatch --job-name="${trial_name}_step3_prep" --mail-user="$email" step3a.sh | awk '{print $4}')
                echo "Submitted Step 3 Prep (dense chunking): $jid3_prep"
                
                if [[ "$run_MVT" == "True" || "$dense_mesh" == "True" ]]; then
                    echo "Dense cloud meshing and MVT (step 4) will be automatically submitted after dense chunk prep."
                fi  
            else
                echo "Skipping Dense Cloud Reconstruction. Set run_dense=True in configs.sh if this step is desired" 
                if [[ "$run_MVT" == "True" || "$dense_mesh" == "True" ]]; then
                    jid4=$(sbatch --job-name="${trial_name}_step4" --mail-user="$email" step4.sh | awk '{print $4}')
                    echo "Submitted step 4 (merging, MVT, and Meshing): $jid4"
                fi            
            fi
            
        fi
    fi
    
    echo "For ${trial_name}, jobs are: ${jid1}, ${jid2},${jid3_prep},${chunk_ids},${jid4}. Saved to jobids.txt"
    echo $(date "+%Y-%m-%d %H:%M:%S") >> "${PROJECT_DIR}/jobids.txt"
    echo "Part 1 Job IDs for ${trial_name}:: Feature Extract/Match: ${jid1}, Sparse prep: ${jid2}" >> "${PROJECT_DIR}/jobids.txt"
    echo "Part 2 Job IDs for ${trial_name}:: Dense chunk prep: ${jid3_prep}, Dense mesh and MVT: ${jid4}" >> "${PROJECT_DIR}/jobids.txt"
done