# Set the directory path to the folder containing your files
$folderPath = "C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\calibration\parent_follow\left"

# Iterate over all files in the folder
Get-ChildItem -Path $folderPath | ForEach-Object {
    $fileName = $_.Name
    # Check if the file name doesn't already start with "right"
    if ($fileName -notlike "left*") {
        $newName = "left" + $fileName
        Rename-Item -Path $_.FullName -NewName $newName
    }
}
