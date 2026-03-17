import numpy as np

# --------------------------
# Helper functions
# --------------------------

def quat_to_rotmat(q):
    """Convert quaternion (qw, qx, qy, qz) to rotation matrix"""
    qw, qx, qy, qz = q
    R = np.array([
        [1-2*(qy**2+qz**2),   2*(qx*qy - qz*qw),   2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw),   1-2*(qx**2+qz**2),   2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw),   2*(qy*qz + qx*qw),   1-2*(qx**2+qy**2)]
    ])
    return R

def camera_center(q, t):
    """Compute camera center in world coordinates"""
    R = quat_to_rotmat(q)
    t = np.array(t).reshape(3,1)
    C = - R.T @ t
    return C.flatten()

# --------------------------
# Read images.txt
# --------------------------

images_file = "images.txt"  # replace with path to your images.txt
camera_positions = {}

with open(images_file, 'r') as f:
    lines = f.readlines()

for line in lines:
    if line.startswith('#') or len(line.strip()) == 0:
        continue
    parts = line.strip().split()
    if len(parts) < 10:
        continue  # skip malformed lines

    image_name = parts[9]
    qw, qx, qy, qz = map(float, parts[1:5])
    tx, ty, tz = map(float, parts[5:8])
    
    camera_positions[image_name] = camera_center([qw,qx,qy,qz], [tx,ty,tz])

# --------------------------
# Compute left/right distances
# --------------------------

distances = []

for name in camera_positions:
    if "left" in name:
        pair_name = name.replace("left", "right")
        if pair_name in camera_positions:
            C_left = camera_positions[name]
            C_right = camera_positions[pair_name]
            dist = np.linalg.norm(C_left - C_right)
            distances.append((name, pair_name, dist))

# --------------------------
# Print results
# --------------------------

for left, right, dist in distances:
    print(f"{left} ↔ {right}: {dist:.4f} units")
    
if distances:
    mean_dist = np.mean([d[2] for d in distances])
    print(f"\nAverage baseline distance: {mean_dist:.4f} units")