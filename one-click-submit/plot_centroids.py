import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from collections import defaultdict

########

annotations_path = "/scratch/alpine/maha7624/3D_Tracking/2024_FF/JM_151_base3/tracks/centroids_R.npy"
images_folder = "/scratch/alpine/maha7624/3D_Tracking/2024_FF/JM_151_base3/images/right"
output_folder = "/scratch/alpine/maha7624/3D_Tracking/2024_FF/JM_151_base3/check_centroids"

image_prefix = "right_"   # or "right_"
image_ext = ".jpg"
zero_pad = 4             # left_0001.jpg

os.makedirs(output_folder, exist_ok=True)

# Load annotations
ann = np.load(annotations_path, allow_pickle=True).item()
# Print first 10 frame entries
for i, (frame_idx, objects) in enumerate(sorted(ann.items())):
    if i >= 10:
        break

# --- Plot each frame ---

for frame_idx, objects in sorted(ann.items()):

    if not objects:  # skip empty frames
        continue

    image_name = f"{image_prefix}{frame_idx:0{zero_pad}d}{image_ext}"
    image_path = os.path.join(images_folder, image_name)

    if not os.path.exists(image_path):
        print(f"Warning: Image not found: {image_name}")
        continue

    image = mpimg.imread(image_path)

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.imshow(image)

    for obj_id, (x, y) in objects.items():
        print(f"Frame {frame_idx}: {objects}")
        print("Image shape:", image.shape)  # (H, W, C)
        print("Point:", x, y)
        ax.scatter(x, y, s=8, c="red", marker="+")
        ax.text(
            x + 5,
            y - 5,
            str(obj_id),
            color="white",
            fontsize=9,
            weight="bold"
        )

    ax.set_title(f"Frame {frame_idx}")
    ax.axis("off")

    output_path = os.path.join(output_folder, image_name)
    plt.savefig(output_path, bbox_inches="tight", pad_inches=0, dpi=300)
    plt.close()

# LINUX Code for stitching images together
#cd /path/to/your/images

#n=1
#for f in $(ls *.jpg | sort); do
#    printf -v new "%04d.jpg" "$n"
#    mv -n -- "$f" "$new"
#    ((n++))
#done

#ffmpeg -framerate 3 -i %04d.jpg -vf "pad=ceil(iw/2)*2:ceil(ih/2)*2,fps=3,format=yuv420p" output.mp4
