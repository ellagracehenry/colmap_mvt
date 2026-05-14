#!/bin/bash -l
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=200G
#SBATCH --time=4:00:00
#SBATCH --output=./logs/%j.out
#SBATCH --error=./logs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

module purge
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env
echo "glomap mamba environment activated"

PROJECT_DIR="${PROJECT_DIR}"
MERGED_OUTPUT="${PROJECT_DIR}/dense/fused_chunked_merged.ply"
sparse_dir="$PROJECT_DIR/sparse_merged"

chunk_dir="${PROJECT_DIR}/chunks"
cd "$scripts_dir"
num_chunks=$(find "$chunk_dir" -maxdepth 1 -mindepth 1 -type d | wc -l)


echo "Merging chunked point clouds..."
python3 merge_chunked_ply.py \
  --project_dir "${PROJECT_DIR}" \
  --num_chunks ${num_chunks} \
  --output "${MERGED_OUTPUT}" \
  --vox_size 0.005 \
  --deduplicate 

echo "Merge complete: ${MERGED_OUTPUT}"

# Get the merged sparse model
model_path="${sparse_dir}/cross_ABC"


if [[ "$run_MVT" == True ]]; then
    if [ -n "$model_path" ]; then
        echo "Merged sparse model is $model_path."
        cp "${MERGED_OUTPUT}" "${model_path}/fused.ply"
        echo "Copied fused_chunked_merged.ply into $model_path for MVT usage"
    else
        echo "No sparse model called 'cross_ABC' found!" 
    fi
fi

echo 'Moving onto Automatic Mask Cleaning & MVT'

if [ "$run_MMC" = True ]; then
    cd herbfishCV
    mamba deactivate 
    mamba activate /projects/maha7624/software/anaconda/envs/herbfishCV

    # Clean Left Masks
    adj_frames_L="${PROJECT_DIR}/images/left"
    cmdL=(
        python multi_dataset_builder.py
        --manual
        --errors-obs-id="$observation_id_L"
        --errors-csv-filepath="$errors_csv_path"
        --masks-filepath="$mask_path_L"
        --annot-filepath="$annotations_L"
        --images-dirpath="$adj_frames_L"
        --extracted-fps="$extracted_fps"
        --final-fps="$final_fps" 
        --ignore-missing-observation-ids
    )
    if [[ "$run_AMC" == "False" ]]; then
        cmdL+=(--no-auto)
    fi
    # Run the mask cleaning command
    printf 'Running command:\n'
    printf '  %q' "${cmdL[@]}"
    printf '\n'
    "${cmdL[@]}"

    # Clean Right Masks
    adj_frames_R="${PROJECT_DIR}/images/right"
    cmdR=(
        python multi_dataset_builder.py
        --manual
        --errors-obs-id="$observation_id_R"
        --errors-csv-filepath="$errors_csv_path"
        --masks-filepath="$mask_path_R"
        --annot-filepath="$annotations_R"
        --images-dirpath="$adj_frames_R"
        --extracted-fps="$extracted_fps"
        --final-fps="$final_fps" 
        --ignore-missing-observation-ids
    )
    
    if [[ "$run_AMC" == "False" ]]; then
        cmdR+=(--no-auto)
    fi
    
    # Run the mask cleaning command
    printf 'Running command:\n'
    printf '  %q' "${cmdR[@]}"
    printf '\n'
    "${cmdR[@]}"

    
    # Find latest left directory of cleaned masks
    export_dir_L="$ROOT_DIR/exports/$observation_id_L"
    latest_run_dir_L=""
    for d in $(find "$export_dir_L" -maxdepth 1 -type d -name "run_*" | sort -V -r); do
        if [ -f "$d/dataset_coco/annotations/instances_train.json" ]; then
            latest_run_dir_L="$d"
            break
        fi
    done
    if [ -z "$latest_run_dir_L" ]; then
        echo "ERROR: No valid run with instances_train.json in $export_dir_L"
    fi
    
    # Find latest right directory of cleaned masks
    export_dir_R="$ROOT_DIR/exports/$observation_id_R"
    latest_run_dir_R=""
    for d in $(find "$export_dir_R" -maxdepth 1 -type d -name "run_*" | sort -V -r); do
        if [ -f "$d/dataset_coco/annotations/instances_train.json" ]; then
            latest_run_dir_R="$d"
            break
        fi
    done
    if [ -z "$latest_run_dir_R" ]; then
        echo "ERROR: No valid run with instances_train.json in $export_dir_R"
    fi
    
    # Copy cleaned coco masks to the project folder
    coco_L="$latest_run_dir_L/dataset_coco/annotations/instances_train.json"
    coco_R="$latest_run_dir_R/dataset_coco/annotations/instances_train.json"
    new_coco_L="$PROJECT_DIR/instances_train_L.json"
    new_coco_R="$PROJECT_DIR/instances_train_R.json"
    
    if [ -f "$coco_L" ]; then
        echo "Copying $coco_L → $new_coco_L"
        cp "$coco_L" "$new_coco_L"
    else
        echo "No cleaned left masks available. Check AMC results"
    fi
    
    if [ -f "$coco_R" ]; then
        echo "Copying $coco_R → $new_coco_R"
        cp "$coco_R" "$new_coco_R"
    else
        echo "No cleaned right masks available. Check AMC results"
    fi
    
    if [ "$run_MVT" = True ]; then
        mamba deactivate
        mamba activate /projects/maha7624/software/anaconda/envs/mvt_env
        cd "$scripts_dir"
        
        # Run MVT with new format
        cmd2=(
        python runMVT.py
        --project_dir="$PROJECT_DIR"
        --trial_name="$trial_name"
        --masks_path_L="$new_coco_L"
        --masks_path_R="$new_coco_R"
        --extracted_fps=$extracted_fps
        --final_fps=$final_fps
        --world_distance=$world_distance
        --err_threshold=$err_threshold 
        --used_AMC
        )
    
        
        if [[ "$extract_centroids" == "False" ]]; then
            cmd2+=(--no_extract_centroids)
        fi
        #if [[ "$run_dense" == "False" ]]; then
        #    cmd2+=(--no_run_dense)
        #fi
    
        if [[ "$interpolate_points" == "False" ]]; then
            cmd2+=(--no_interpolate_points)
        fi    
        printf 'Running command:\n'
        printf '  %q' "${cmd2[@]}"
        printf '\n'
        "${cmd2[@]}"
    fi
    
else
    echo 'Not using Mask Cleaner, good luck!'
    if [ "$run_MVT" = True ]; then
        mamba deactivate 
        mamba activate /projects/maha7624/software/anaconda/envs/mvt_env
        
        # Extract mask file extensions
        ext_L="${mask_path_L##*.}"
        ext_R="${mask_path_R##*.}"
        ext_L="${ext_L,,}"
        ext_R="${ext_R,,}"

        # 1) Ensure extensions match
        if [[ "$ext_L" != "$ext_R" ]]; then
            echo "Error: masks must be of the same file type: .pkl or .json"
            exit 1
        fi


        # Run MVT 
        cmd3=(
        python runMVT.py
        --project_dir="$PROJECT_DIR"
        --trial_name="$trial_name"
        --masks_path_L="$mask_path_L"
        --masks_path_R="$mask_path_R"
        --extracted_fps=$extracted_fps
        --final_fps=$final_fps
        --world_distance=$world_distance
        --err_threshold=$err_threshold
        )
        # 2) Check mask extension type
        if [[ "$ext_L" == "json" ]]; then
            cmd3+=(--used_AMC)
            
        elif [[ "$ext_L" == "pkl" ]]; then
            cmd3+=(--no_AMC)
        else
            echo "Error: unsupported mask file type '$ext_L'"
            exit 1
        fi
        
        if [[ "$extract_centroids" == "False" ]]; then
            cmd3+=(--no_extract_centroids)
        fi
    
        #if [[ "$run_dense" == "False" ]]; then
        #    cmd3+=(--no_run_dense)
        #fi
    
        if [[ "$interpolate_points" == "False" ]]; then
            cmd3+=(--no_interpolate_points)
        fi
        printf 'Running command:\n'
        printf '  %q' "${cmd3[@]}"
        printf '\n'
        "${cmd3[@]}"    
    fi

fi

# Rename unscaled point cloud, if not already done. 
if [ -f "$PROJECT_DIR/dense/fused_chunked_merged.ply" ]; then
    cp "$PROJECT_DIR/dense/fused_chunked_merged.ply" "$PROJECT_DIR/dense/unscaled_fused_merged.ply"
else
    echo "Warning: fused_chunked_merged.ply not found in dense directory, skipping rename."
fi


output_path="${PROJECT_DIR}/dense/${trial_name}_meshed-poisson.ply"

if [ "$dense_mesh" = True ]; then
    # Activate glomap again
    mamba deactivate 
    mamba activate /projects/maha7624/software/anaconda/envs/glomap_env   

    # Mesh dense point cloud with Poisson
    if [ "$run_MVT" = True ]; then
        colmap poisson_mesher --input_path "$PROJECT_DIR/dense/${trial_name}_scaled_fused.ply" --output_path "$output_path" --PoissonMeshing.depth=13
    else
        colmap poisson_mesher --input_path "$PROJECT_DIR/dense/unscaled_fused_merged.ply" --output_path "${PROJECT_DIR}/dense/${trial_name}_unscaled-meshed-poisson.ply"
    fi
fi

if [ -f "$output_path" ]; then
    echo "✓ Poisson mesher complete: $output_path"
else
    echo "✗ Warning: Final poisson mesh not created"
fi