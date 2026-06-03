import sys
import subprocess
from pathlib import Path
import os
import shutil
from renamefiles import main
from datetime import datetime

    
def run_pipeline(
    folder_path_L,
    folder_path_R,
    project_dir,
    vocab_tree_path,
    extracted_fps,
    final_fps,
    rename_images,
    run_feat_ext_match,
    run_sparse,
    run_dense,
    image_list_path=None,
    output_sparse_dir=None
    
):
    import os
    from pathlib import Path

    # Step 2: Subsample, rename & reorganize images
    if rename_images==True:
        main(
            folder_path_L=folder_path_L,
            folder_path_R=folder_path_R,
            project_dir=project_dir,
            extracted_fps=extracted_fps,
            final_fps=final_fps,
        )
    
    # Step 2.1: Set folder paths
    db_path = os.path.join(project_dir, "database.db")
    db_aux_path = os.path.join(project_dir, "database.db-shm")
    img_path = os.path.join(project_dir, "images")
    
    if output_sparse_dir is not None:
        sparse_dir = output_sparse_dir
    else:
        sparse_dir = os.path.join(project_dir, "sparse")

    dense_dir = os.path.join(project_dir, "dense")
    vocab_tree_path = Path(vocab_tree_path)
    

    # Step 3: Run Feature Extraction
    if run_feat_ext_match==True:

        ### Added to remove old db to ensure clean db for re-running ###
        if os.path.exists(db_path):
            print("Removing existing database for clean run...")
            os.remove(db_path)

        print(f"\n[2] Running COLMAP feature extraction (OPENCV camera model)...")
        print(f"  Database: {db_path}")
        print(f"  Image path: {img_path}")
        print(f"  Camera model: OPENCV")
        print(f"  Single camera per folder: 1")
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Starting feature extraction...")

        cmd = [
            "colmap", "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(img_path),
            "--ImageReader.single_camera_per_folder=1",
            "--SiftExtraction.use_gpu=1",
            "--SiftExtraction.gpu_index=0",
            "--ImageReader.camera_model=OPENCV"
        ]
        

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True
        )

        print(result.stdout)

        if not os.path.exists(db_path):
            raise RuntimeError("Feature extraction completed but database.db not found")

        if result.returncode != 0:
            print(f"  ✗ Feature extraction failed:")
            print(result.stderr[-1000:])
            sys.exit(1)

        print(f"  ✓ Feature extraction complete")

    # Step 4: Run Feature Matching
    if run_feat_ext_match==True:
        print(f"\n[3] Running COLMAP feature matching...")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Starting feature matching...")

        if vocab_tree_path.exists():
            print(f"  Using sequential_matcher with vocab_tree (faster)")
            cmd = [
                "colmap", "sequential_matcher",
                "--database_path", str(db_path),
                "--SequentialMatching.vocab_tree_path", str(vocab_tree_path),
                "--SequentialMatching.loop_detection=1",
                "--SequentialMatching.loop_detection_period=10",
                "--SequentialMatching.loop_detection_num_images=50",
                "--SiftMatching.use_gpu=1",
                "--SiftMatching.gpu_index=0"
                ]

        else:
            print(f"  ⚠️  Vocab_tree not found at {vocab_tree_path}")
            print(f"  Using sequential_matcher without vocab_tree (may be slower and less accurate)")
            cmd = [
                "colmap", "sequential_matcher",
                "--database_path", str(db_path),
                "--SequentialMatching.loop_detection=1"
                "--SequentialMatching.loop_detection_period=10",
                "--SequentialMatching.loop_detection_num_images=50"
            ]
        
            
        print(f"  Command: {' '.join(cmd)}")
        print(f"  ⏱️  This may take 30-90 minutes depending on image count...")
        cmd_str = " ".join(cmd)


        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True
        )

        print(result.stdout)

        if os.path.exists(db_aux_path):
            raise RuntimeError("Feature extraction completed but database.db-wbm still present")
            
        if result.returncode != 0:
            print(f"  ✗ Feature matching failed:")
            print(result.stderr[-1000:])
            sys.exit(1)

        print(f"  ✓ Feature matching complete")

    # Step 5: Run Sparse Reconstruction (optimized)
    if run_sparse==True:
        print(f"\n[3] Running sparse reconstruction...")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Starting sparse reconstruction...")
        
        os.makedirs(sparse_dir, exist_ok=True)

        cmd = [
            "colmap", "mapper",
            "--database_path", str(db_path),
            "--image_path", str(img_path),
            "--output_path", str(sparse_dir),
            "--Mapper.tri_min_angle=3",
            "--Mapper.tri_complete_max_reproj_error=3",
            "--Mapper.tri_merge_max_reproj_error=3",
            "--Mapper.ba_global_images_ratio", "1.2",
            "--Mapper.ba_global_points_ratio", "1.2",
            "--Mapper.ba_global_max_num_iterations", "20",
            "--Mapper.ba_global_max_refinements", "3",
            "--Mapper.ba_global_points_freq", "200000"
        ]  
        if image_list_path is not None:
            cmd+= ["--image_list_path", str(image_list_path)]
 
        print(f"  Command: {' '.join(cmd)}")
        print(f"  ⏱️  This may take some time depending on image count...")
        cmd_str = " ".join(cmd)


        # Stream output line-by-line so progress is visible in logs during long runs
        with subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
            for line in proc.stdout:
                print(line, end='', flush=True)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"Sparse reconstruction failed with return code {proc.returncode}")

        print(f"  ✓ Sparse Reconstruction complete")


    
    # Step 6: Run Dense Reconstruction (optimized)
    if run_dense==True:
    
        sparse_merged_dir=Path(project_dir/"sparse_merged")
        model_path=Path(sparse_merged_dir/"cross_ABC_ba")
        
        print(f"Sparse model used is {model_path}.")

        os.makedirs(dense_dir, exist_ok=True)
        print(f"\n[3] Running COLMAP image undistortion...")    
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Starting dense reconstruction (image undistortion)...")
        cmd = [
            "colmap", "image_undistorter",
            "--image_path", str(img_path),
            "--input_path", str(model_path), 
            "--output_path", str(dense_dir),
            "--output_type","COLMAP",
            "--max_image_size=1500"
        ]

        print(f"  Command: {' '.join(cmd)}")
        print(f"  ⏱️  This may take some time depending on image count...")
        cmd_str = " ".join(cmd)


        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True
        )

        print(result.stdout)
            
        if result.returncode != 0:
            print(f"  ✗ Image undistorter failed:")
            print(result.stderr[-1000:])
            sys.exit(1)

        print(f"  ✓ Image undistortion complete")
    
    
        # Patch match stereo
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}]")
        print(f"\n[3] Running COLMAP patch match stereo...")    
        cmd = [
            "colmap", "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.max_image_size=1500",
            "--PatchMatchStereo.geom_consistency=false",
            "--PatchMatchStereo.filter=true",
            "--PatchMatchStereo.window_step=2",
            "--PatchMatchStereo.num_iterations=3",
            "--PatchMatchStereo.num_samples=15",
            "--PatchMatchStereo.gpu_index=0,1"
        ]

        print(f"  Command: {' '.join(cmd)}")
        print(f"  ⏱️  This may take some time depending on image count...")
        cmd_str = " ".join(cmd)

        result = subprocess.run(
            cmd_str,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True
            )
        
        print(result.stdout)

        if result.returncode != 0:
            print(f"  ✗ Patch Match Stereo failed:")
            print(result.stderr[-1000:])
            sys.exit(1)

        print(f"  ✓ Patch Match Stereo complete")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}]")
        print(f"\n[3] Running COLMAP stereo fusion...")  
        cmd=[
        "colmap", "stereo_fusion",
        "--workspace_path", str(dense_dir),
        "--workspace_format", "COLMAP",
        "--input_type","photometric",
        "--output_path", str(os.path.join(dense_dir,"fused.ply")),
        "--StereoFusion.max_image_size=1500"
        ]
    
        print(f"  Command: {' '.join(cmd)}")
        print(f"  ⏱️  This may take some time depending on image count...")
        cmd_str = " ".join(cmd)

        result = subprocess.run(
            cmd_str,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True
            )
        
        print(result.stdout)
  
        if result.returncode != 0:
            print(f"  ✗ Stereo fusion failed:")
            print(result.stderr[-1000:])
            sys.exit(1)

        print(f"  ✓ Stereo fusion complete")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Running image reorganization --> dense reconstruction')
    parser.add_argument('--folder_path_L', type=str, required=True, help='Path left frames dir')
    parser.add_argument('--folder_path_R', type=str, required=True, help='Path to right frames dir')
    parser.add_argument('--project_dir', type=str, required=True, help='Project directory for reconstruction')
    parser.add_argument('--vocab_tree_path', type=str, required=True, help='Path to vocab tree')
    parser.add_argument('--extracted_fps', type=int, default=3, help='Original FPS of synced & extracted images')
    parser.add_argument('--final_fps', type=int, default=1, help='Overlap ratio for temporal chunking')
    parser.add_argument('--rename_images', action='store_true',
                    help='Subsample, rename, and reorganize images')
    parser.add_argument('--no_rename_images', dest='rename_images',
                    action='store_false',
                    help='Skip image reorganization')
    parser.set_defaults(rename_images=True)

    parser.add_argument('--run_feat_ext_match', action='store_true',
                    help='Run feature extraction and matching')
    parser.add_argument('--no_run_feat_ext_match', dest='run_feat_ext_match',
                    action='store_false',
                    help='Skip Feature Extraction & Matching')
    parser.set_defaults(run_feat_ext_match=True)
    
    parser.add_argument('--run_sparse', action='store_true',
                    help='Run sparse reconstruction')
    parser.add_argument('--no_run_sparse', dest='run_sparse',
                    action='store_false',
                    help='Skip sparse reconstruction')
    parser.set_defaults(run_sparse=True)   
    
    parser.add_argument('--run_dense', action='store_true',
                    help='Run dense reconstruction')
    parser.add_argument('--no_run_dense', dest='run_dense',
                    action='store_false',
                    help='Skip dense reconstruction')
    parser.set_defaults(run_dense=True)  

    parser.add_argument('--image_list_path', type=str, default=None)
    parser.add_argument('--output_sparse_dir', type=str, default=None) 

    args = parser.parse_args()
    
    run_pipeline(
        folder_path_L=args.folder_path_L,
        folder_path_R=args.folder_path_R,
        project_dir=args.project_dir,
        vocab_tree_path=args.vocab_tree_path,
        extracted_fps=args.extracted_fps,
        final_fps=args.final_fps,
        rename_images=args.rename_images,
        run_feat_ext_match=args.run_feat_ext_match,
        run_sparse=args.run_sparse,
        run_dense=args.run_dense,
        image_list_path=args.image_list_path,
        output_sparse_dir=args.output_sparse_dir
    )
