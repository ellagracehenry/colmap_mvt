#!/bin/bash
#SBATCH --partition aa100 # Partition or queue
#SBATCH --job-name=dense_reconstruction # Job name
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --ntasks=42 # GPU's * 21 is max tasks on sinteractive
#SBATCH --time=12:00:00 # Time limit hrs:min:sec
#SBATCH --output=log_%j.out # Standard output and error log
#SBATCH --error=log_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=elhe2720@colorado.edu #Change this to your email address

#load conda environment
module purge
module load miniforge
conda activate glomap_env
echo "glomap conda environment activated"

colmap image_undistorter --image_path project_name/images --input_path project_name/sparse/0 --output_path project_name/dense --output_type COLMAP --max_image_size 2000
echo "image distorter complete"
colmap patch_match_stereo --workspace_path project_name/dense --workspace_format COLMAP --PatchMatchStereo.geom_consistency true
echo "patch match stereo complete"
colmap stereo_fusion --workspace_path project_name/dense --workspace_format COLMAP --input_type geometric --output_path project_name/dense/fused.ply
echo "stereo_fusion complete"
colmap poisson_mesher --input_path project_name/dense/fused.ply --output_path project_name/dense/meshed-poisson.ply
echo "poisson mesher complete"
colmap delaunay_mesher --input_path project_name/dense --output_path project_name/dense/meshed-delaunay.ply
echo "delaunay mesher complete"
