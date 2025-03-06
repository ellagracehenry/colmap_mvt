# Set the directory path to the folder containing your files
$folderPath = "C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\subset_images\right"

# Iterate over all files in the folder
Get-ChildItem -Path $folderPath | ForEach-Object {
    $fileName = $_.Name
    # Check if the file name doesn't already start with "right"
    if ($fileName -notlike "right*") {
        $newName = "right" + $fileName
        Rename-Item -Path $_.FullName -NewName $newName
    }
}
