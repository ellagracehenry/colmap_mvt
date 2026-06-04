#!/usr/bin/env bash

set -euo pipefail

# ============================================
# Usage:
#   ./pull_trials.sh configs.sh
#
# Assumptions:
#   configs.sh defines:
#       root_dir="/path/to/root"
#       trial_names=("trialA" "trialB")
#
# This script:
#   1. Creates tar.gz archives remotely
#   2. Transfers them locally
#   3. Uses one SSH authentication session
# ============================================

CONFIG_FILE="${1:-configs.sh}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Config file not found: $CONFIG_FILE"
    exit 1
fi

# Load config
source "$CONFIG_FILE"

# ============================================
# USER SETTINGS
# ============================================

REMOTE_USER="maha7624"
REMOTE_HOST="login.rc.colorado.edu"

# Optional SSH port
# SSH_PORT=22

# Where archives should be temporarily created on remote HPC
REMOTE_TMP_DIR="/scratch/alpine/maha7624/3D_Tracking/2024_FF/tmp"

# Local destination
LOCAL_DEST="/Users/mad4rosie/Downloads/test_transfer"

mkdir -p "$LOCAL_DEST"

# ============================================
# SSH OPTIONS
# ============================================

SSH_CONTROL_PATH="/tmp/ssh_mux_%h_%p_%r"

SSH_OPTS=(
    -o ControlMaster=auto
    -o ControlPath="$SSH_CONTROL_PATH"
    -o ControlPersist=1h
)

# If needed:
# SSH_OPTS+=(-p "$SSH_PORT")

# ============================================
# OPEN MASTER CONNECTION
# ============================================

echo "Opening persistent SSH connection..."

ssh "${SSH_OPTS[@]}" -fN \
    "${REMOTE_USER}@${REMOTE_HOST}"

# ============================================
# CREATE REMOTE TEMP DIR
# ============================================

ssh "${SSH_OPTS[@]}" \
    "${REMOTE_USER}@${REMOTE_HOST}" \
    "mkdir -p '$REMOTE_TMP_DIR'"

# ============================================
# PROCESS EACH TRIAL
# ============================================

for trial_name in "${trial_names[@]}"; do

    echo "========================================"
    echo "Processing: $trial_name"
    echo "========================================"

    REMOTE_TRIAL_DIR="${root_dir}/${trial_name}"

    REMOTE_ARCHIVE="${REMOTE_TMP_DIR}/${trial_name}.tar.gz"

    # ----------------------------------------
    # Remote packaging script
    # ----------------------------------------

    ssh "${SSH_OPTS[@]}" \
        "${REMOTE_USER}@${REMOTE_HOST}" \
        bash <<EOF

set -euo pipefail

trial_dir="${REMOTE_TRIAL_DIR}"
trial_name="${trial_name}"
archive="${REMOTE_ARCHIVE}"

if [[ ! -d "\$trial_dir" ]]; then
    echo "Missing trial directory: \$trial_dir"
    exit 1
fi

cd "\$trial_dir"

# Find highest merge_xxxx folder
latest_merge=\$(find sparse_merged \
    -maxdepth 1 \
    -type d \
    -name "merge_*" | sort | tail -n 1)

echo "Using merge folder: \$latest_merge"

# Build tarball
tar -czf "\$archive" \
    configs_used*.sh \
    dense/\${trial_name}_meshed-poisson.ply \
    dense/unscaled_fused_merged.ply \
    \${trial_name}_tracks_3d_output.csv \
    \${trial_name}_3d_tracks.ply \
    "\$latest_merge" \
    database.db \
    2>/dev/null || true

echo "Created archive:"
echo "\$archive"

EOF

    # ----------------------------------------
    # Transfer archive locally
    # ----------------------------------------

    echo "Transferring archive..."

    rsync -avhP \
        -e "ssh ${SSH_OPTS[*]}" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_ARCHIVE}" \
        "${LOCAL_DEST}/"

done

# ============================================
# OPTIONAL CLEANUP
# ============================================

echo "Cleaning up remote temp archives..."

ssh "${SSH_OPTS[@]}" \
    "${REMOTE_USER}@${REMOTE_HOST}" \
    "rm -rf '$REMOTE_TMP_DIR'"

# ============================================
# CLOSE MASTER CONNECTION
# ============================================

echo "Closing SSH master connection..."

ssh -O exit \
    -o ControlPath="$SSH_CONTROL_PATH" \
    "${REMOTE_USER}@${REMOTE_HOST}" || true

echo "Done."