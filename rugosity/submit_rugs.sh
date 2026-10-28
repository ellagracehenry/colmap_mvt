#!/bin/bash -l
#SBATCH --job-name=rugosity_submission
#SBATCH --partition=acpu
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=0:01:00
#SBATCH --output=./ehclogs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./ehclogs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --qos=cpu-normal
#SBATCH --account=ucb689_peak2
#SBATCH --mail-user=elhe2720@colorado.edu


configs="rugs_configs.txt"

while read -r obsID; do
    [[ -z "$obsID" ]] && continue # skip blanks
    sbatch --job-name="rugosity_${obsID}" batch_rugs.sh "$obsID"
done < "$configs"