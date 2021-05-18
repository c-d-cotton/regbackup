# Summary
Allows for regular backup of files

# Functions
Can run several functions
run/backupdirs.py: Backs up whole directories
run/backupcode.py: Backs up only specific files with the same structure as where the files came from
run/copyziplatest.py: Copies unzipped backups to a zipped backup in a separate location

backupdirs and backupcode both require the following arguments:
- backuprootdir: This is the directory where the backups will save
- --files_infile or --files_single or --files_aslines etc.: This specifies the code in the case of backupcode and the directories in the case of backupdirs
- frequencies specified by -f M5 -f H1 -f d1 -f d10 -f m1: At least one of these must be specified. These create backups at different frequencies in the backup folder

