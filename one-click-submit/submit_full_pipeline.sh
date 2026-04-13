#!/bin/bash -l
set -e

# Read from configs
source configs.sh

# First, check that the correct lengths of essential config values are provided
arrays_to_check=(
  frames_paths_L
  frames_paths_R
  modes
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
    mode=${modes[$i]}
    extracted_fps=${extracted_fpss[$i]}
    final_fps=${final_fpss[$i]}
    
    
    echo "======================================"
    echo "Submitting trial: $trial_name"
    echo "======================================"
    PROJECT_DIR="${ROOT_DIR}/${trial_name}" 
    if [ ! -d "${PROJECT_DIR}" ]; then
        mkdir "${PROJECT_DIR}"
    fi
    
    cp configs.sh "${ROOT_DIR}/${trial_name}/configs_used.sh"
    
    export trial_name frames_path_L frames_path_R mask_path_L mask_path_R observation_id_L observation_id_R PROJECT_DIR \
      annotations_L annotations_R world_distance ROOT_DIR scripts_dir vocab_tree_path extracted_fps final_fps  email \
      rename_images run_feat_ext_match run_sparse run_dense interpolate_points extract_centroids run_MMC run_AMC run_MVT err_threshold errors_csv_path mode

    if [[ "$rename_images" == "True" || "$run_feat_ext_match" == "True" ]]; then
        jid1=$(sbatch --job-name="${trial_name}_step1" --mail-user="$email" --mail-type=ALL step1.sh | awk '{print $4}')
        echo "Submitted step1 (Image organization and feature matching): $jid1"

        if [[ "$run_sparse" == "True" ]]; then
            if [[ "$mode" == "snorkel" ]]; then
                jid2=$(sbatch --job-name="${trial_name}_step2" --dependency=afterok:$jid1 --mail-user="$email" --mail-type=ALL --time=24:00:00 step2.sh | awk '{print $4}')
                echo "Submitted step2: Sparse Reconstruction for Snorkel (COLMAP), allotted 24hrs: $jid2"
            else
                jid2=$(sbatch --job-name="${trial_name}_step2" --dependency=afterok:$jid1 --mail-user="$email" --mail-type=ALL --time=5:00:00 step2.sh | awk '{print $4}')
                echo "Submitted step2: Sparse Reconstruction for Scuba (GLOMAP), allotted 5hrs: $jid2"
            fi
            
            if [[ "$run_dense" == "True" || "$run_MVT" == "True" ]]; then
                jid3=$(sbatch --job-name="${trial_name}_step3" --dependency=afterok:$jid2 --mail-user="$email" --mail-type=ALL step3.sh | awk '{print $4}')
                echo "Submitted step3 (Dense cloud, MVT, and Meshing): $jid3"
            else
                echo "Skipping Step 3 (Dense cloud, MVT, and meshing). Set run_dense or run_MVT to True if this is needed"
            fi
        else
            echo "Skipping Step 2 (sparse cloud). Set run_sparse to True if this is needed"
            if [[ "$run_dense" == "True" || "$run_MVT" == "True" ]]; then
                jid3=$(sbatch --job-name="${trial_name}_step3" --dependency=afterok:$jid1 --mail-user="$email" --mail-type=ALL step3.sh | awk '{print $4}')
                echo "Submitted step3 (Dense cloud, MVT, and Meshing): $jid3"
            else
                echo "Skipping Step 3 (Dense cloud, MVT, and meshing). Set run_dense or run_MVT to True if this is needed"
            fi
        fi
    else
        echo "Skipping Step 1 (Image reorganization and feature matching). Set rename_images or run_feat_ext_match, to True if needed"
        if [[ "$run_sparse" == "True" ]]; then
            if [[ "$mode" == "snorkel" ]]; then
                jid2=$(sbatch --job-name="${trial_name}_step2" --mail-user="$email" --mail-type=ALL --time=24:00:00 step2.sh | awk '{print $4}')
                echo "Submitted step2: Sparse Reconstruction for Snorkel (COLMAP), allotted 24hrs: $jid2"
            else
                jid2=$(sbatch --job-name="${trial_name}_step2" --mail-user="$email" --mail-type=ALL --time=5:00:00 step2.sh | awk '{print $4}')
                echo "Submitted step2: Sparse Reconstruction for Scuba (GLOMAP), allotted 5hrs: $jid2"
            fi
            if [[ "$run_dense" == "True" || "$run_MVT" == "True" ]]; then
                jid3=$(sbatch --job-name="${trial_name}_step3" --dependency=afterok:$jid2 --mail-user="$email" --mail-type=ALL step3.sh | awk '{print $4}')
                echo "Submitted step3 (Dense cloud, MVT, and Meshing): $jid3"
            else
                echo "Skipping Step 3 (Dense cloud, MVT, and meshing). Set run_dense or run_MVT to True if this is needed"
            fi
        else
            echo "Skipping Step 2 (sparse cloud). Set run_sparse to True if this is needed"
            jid3=$(sbatch --job-name="${trial_name}_step3" --mail-user="$email" --mail-type=ALL step3.sh | awk '{print $4}')
            echo "Submitted step3 (Dense cloud, MVT, and Meshing): $jid3"
        fi
    fi
done
