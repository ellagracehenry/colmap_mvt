#!/bin/bash
#SBATCH --partition amilan # Partition or queue
#SBATCH --job-name=sparse_reconstruction # Job name
#SBATCH --nodes=1
#SBATCH --ntasks=28 # GPU's * 21 is max tasks on sinteractive
#SBATCH --time=3:00:00 # Time limit hrs:min:sec
#SBATCH --output=log_%j.out # Standard output and error log
#SBATCH --error=log_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=elhe2720@colorado.edu #Change this to your email address
#SBATCH --qos=normal

#load conda environment
module purge
module load miniforge
conda activate glomap_env
echo "colmap conda environment activated"

glomap mapper --image_path project_name/images --database_path project_name/database.db --output_path project_name/sparse
echo "sparse reconstruction complete"
