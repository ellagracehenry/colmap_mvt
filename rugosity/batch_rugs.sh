#!/bin/bash -l
#SBATCH --job-name=rugosity
#SBATCH --partition=acpu
#SBATCH --nodes=1
#SBATCH --ntasks=5
#SBATCH --time=04:00:00
#SBATCH --mem=60G
#SBATCH --output=./logs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./logs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --qos=cpu-normal
#SBATCH --account=ucb689_peak2
#SBATCH --mail-user=elhe2720@colorado.edu


set -euo pipefail

## Parameters ##

base_dir="/scratch/alpine/elhe2720/colmap/improve_snorkel/3DTracking_Oneclick/2023_FF"
script_dir="/scratch/alpine/elhe2720/colmap/improve_snorkel/3DTracking_Oneclick/2023_FF/rugosity"


# Work line by line through the configs file #

obsID="${1:?Usage: sbatch batch_rugs.sh <obsID>}"

echo "Processing Observation: $obsID"

mesh="${base_dir}/${obsID}/final_files/${obsID}_meshed-poisson.ply"
tracks="${base_dir}/${obsID}/final_files/${obsID}_3d_tracks.ply"
tracks_csv="${base_dir}/${obsID}/final_files/${obsID}_tracks_3d_output.csv"
output_dir="/scratch/alpine/elhe2720/colmap/improve_snorkel/3DTracking_Oneclick/2023_FF/rugosity/spotlight_output_1m"

mkdir -p "$output_dir"

# Load raycasting environment #

module purge
module load miniforge
conda activate raycast

cd "$script_dir"

# Run raycasting script #
python rugcalc_2d_reefanchored.py --mesh_path "$mesh" --trajectory_ply "$tracks" --trajectory_csv "$tracks_csv" --output_path "${output_dir}/${obsID}_rugosity.csv" --radius 1




