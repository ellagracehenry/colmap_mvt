#!/bin/bash
#SBATCH --partition aa100 # Partition or queue
#SBATCH --job-name=feature_extract_match # Job name
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=21 # GPU's * 21 is max tasks on sinteractive
#SBATCH --time=3:00:00 # Time limit hrs:min:sec
#SBATCH --output=log_%j.out # Standard output and error log
#SBATCH --error=log_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=elhe2720@colorado.edu #Change this to your email address

#load conda environment
module purge
module load miniforge
conda activate glomap_env
echo "glomap conda environment activated"

colmap feature_extractor --database_path project_name/database.db --image_path project_name/images --ImageReader.single_camera_per_folder=1 --SiftExtraction.use_gpu=1 --SiftExtraction.gpu_index=0 --ImageReader.camera_model=OPENCV
echo "feature extractor complete"
colmap sequential_matcher --database_path project_name/database.db --SequentialMatching.vocab_tree_path=vocab_tree_flickr100K_words256K.bin --SequentialMatching.loop_detection=1  --SequentialMatching.loop_detection_period=10 --SequentialMatching.loop_detection_num_images=50 --SiftMatching.use_gpu=1 --SiftMatching.gpu_index=0
echo "feature matcher complete"
