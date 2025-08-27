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
#SBATCH --qos=normal

#load conda environment
module purge
module load miniforge
conda activate glomap_env
echo "glomap conda environment activated"

colmap poisson_mesher --input_path project_name/dense/rescaled_model.ply --output_path project_name/dense/rescaled_meshed-poisson.ply
echo "poisson mesher complete"

#Currently not working... 
#colmap delaunay_mesher --input_path project_name/dense --output_path project_name/dense/meshed-delaunay.ply
#echo "delaunay mesher complete"
