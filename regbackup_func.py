#!/usr/bin/env python3
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

__projectdir__ = Path(os.path.dirname(os.path.realpath(__file__)) + '/')


sys.path.append(str(__projectdir__ / Path('submodules/allcode-list/')))
from getallcode_func import getallcode

# General Auxilliary Backup Functions:{{{1
def md5Checksum(filePath):
    """
    Taken from https://www.joelverhagen.com/blog/2011/02/md5-hash-of-file-in-python/ on 20171226.
    """
    import hashlib
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def twofilesaresame(filename1, filename2):
    checksum1 = md5Checksum(filename1)
    checksum2 = md5Checksum(filename2)

    if checksum1 == checksum2:
        return(True)
    else:
        return(False)
    
def rsyncfolders(folderstosync, backuprootfolder, namesdict = None, excludefolders = None):
    """
    This document provides functions to do backups regularly
    I allow for different possible backups
    This function is one potential form of backup (that I use myself)
    """
    if namesdict is None:
        namesdict = {}
    if not os.path.isdir(backuprootfolder):
        os.mkdir(backuprootfolder)
    for folder in folderstosync:
        if folder not in namesdict:
            namesdict[folder] = os.path.basename(os.path.abspath(folder))

        # need to add separator on the end otherwise rsync doesn't work well
        sourcefolder = os.path.abspath(folder) + os.sep
        destfolder = os.path.join(backuprootfolder, namesdict[folder]) + os.sep

        # initial rsync options
        rsynclist = ['rsync', '-a', '--delete']
        if excludefolders is not None:
            # make a copy
            excludefolders2 = []
            for excludefolder in excludefolders:
                if excludefolder[0] == '/':
                    # can't give --exclude as fullpath
                    # needs to be a relative path to the directory I'm backing up
                    if excludefolder.startswith(sourcefolder):
                        excludefolders2.append(excludefolder[len(sourcefolder): ])
                else:
                    excludefolders2.append(excludefolder)
                    

            # I like to not rsync the pattern '*/submodules/*'
            # note that I need to add "" around excludefolder otherwise doesn't seem to work with cron
            rsynclist = rsynclist + ['--exclude "' + excludefolder + '"' for excludefolder in excludefolders2]
            rsynclist = rsynclist + ['--delete-excluded']

        rsynclist = rsynclist + [sourcefolder, destfolder]

        # rsync across
        # seems that rsync with /bin/sh doesn't have --exclude command embedded
        subprocess.call(' '.join(rsynclist), shell = True)

    # delete old folders
    goodfolders = [namesdict[folder] for folder in namesdict]
    badfolders = [folder for folder in os.listdir(backuprootfolder) if folder not in goodfolders]
    for folder in badfolders:
        folder2 = os.path.join(backuprootfolder, folder)
        subprocess.call(['chmod', '-R', '777', folder2])
        shutil.rmtree(folder2)

    
# Main 2 Backup Methods:{{{1
def backupfiles(backuprootfolder):
    """
    Back up only files marked as code - not whole folders
    """
    # get all code
    if not os.path.isfile(__projectdir__ / Path('paths/allcode.txt')):
        raise ValueError('Need to define paths/allcode.txt to run backup.')
    with open(__projectdir__ / Path('paths/allcode.txt')) as f:
        text = f.read()
    parselist = text.splitlines()
    parselist = [line.replace('~', os.path.expanduser('~')) for line in parselist if not line.startswith('#')]
    allcode = getallcode(parselist)

    # remove common paths from allcode
    commonprefix = os.path.commonprefix(allcode)

    # get allcode without a prefix
    allcode_noprefix = [filename[len(commonprefix): ] for filename in allcode]

    # get list of files in current backuprootfolder
    existingfiles = []
    existingdirs = []
    for root, dirs, files in os.walk(str(backuprootfolder), topdown=False):
        for name in files:
            existingfiles.append(os.path.join(root, name))
        for name in dirs:
            existingdirs.append(os.path.join(root, name))

    # get existing files iwthout prefix
    existingfiles_noprefix = [filename[len(str(backuprootfolder)) + 1: ] for filename in existingfiles]

    # add/update files in allcode
    for filename in allcode_noprefix:
        oldloc = os.path.join(commonprefix, filename)
        newloc = os.path.join(backuprootfolder, filename)

        if os.path.isfile(newloc):
            if twofilesaresame(oldloc, newloc):
                continue
            else:
                os.remove(newloc)

        # create directory if not exist
        if not os.path.isdir(os.path.dirname(newloc)):
            os.makedirs(os.path.dirname(newloc))
        
        # if not continued since the same then copy over file
        shutil.copyfile(oldloc, newloc)

    # delete existing files if not in allcode
    for filename in existingfiles_noprefix:
        if filename not in allcode_noprefix:
            os.remove(os.path.join(backuprootfolder, filename))

    # delete empty folders
    for existingdir in existingdirs:
        if len(os.listdir(existingdir)) == 0:
            # note this will only remove folders with no folders in
            # so would not remove dir1 if dir1/dir2 exists
            # but if dir2 contains no folders dir2 would be removed
            # then dir1 could be removed
            os.rmdir(existingdir)


def backupfiles_test():
    backupfiles('~/backupfiles_test/'.replace('~', os.path.expanduser('~')))   


def backupfolders(backuprootfolder):
    """
    Back up whole folders in my code but ignoring a few very specific folders
    """
    with open(__projectdir__ / Path('paths/allcode.txt')) as f:
        paths = f.read().splitlines()

    folderstosync = [p for p in paths if not p.startswith('#')]
    folderstosync = [p.replace('~', '/home/chris') for p in folderstosync]

    # need ** to cover submodules/ and folder/submodules/
    # * only covers folder/submodules/ but not submodules/
    rsyncfolders(folderstosync, backuprootfolder, excludefolders = ['**/submodules/', '**/submodules/', '**/*-external'])


def backupfolders_test():
    backupfolders('~/backupfolders_test/'.replace('~', os.path.expanduser('~')))


# Overall Backup Function:{{{1
def renameoldest(rootfolder, newdate, maxbackups):
    """
    If folder already contains files equivalent to maxbackups, rename the oldest as newdate
    Also verifies that all files are same length as newdate as a basic check
    """
    dirs = os.listdir(rootfolder)
    dirs = sorted(dirs)

    # verify all zips have same length as latestdir
    lengths = [len(folder) for folder in dirs]
    if len(set(lengths)) > 1:
        raise ValueError('More than one length of dirs in folder. Lengths: ' + str(lengths) + '. Folder: ' + str(sourceroot) + '.')

    if len(dirs) >= maxbackups:
        shutil.move(rootfolder / Path(dirs[0]), rootfolder / Path(newdate))

    
def copyziplatest(sourceroot, destroot, maxbackups = None):
    """
    Used when copying over the latest unzipped version of a folder to a new zipped version in a different folder

    If folder already contains files equivalent to maxbackups, delete the oldest
    Also verifies that all files are same length as newdate as a basic check
    """
    dirs = os.listdir(sourceroot)
    dirs = sorted(dirs)
    latestdir = dirs[-1]

    # verify all zips have same length as latestdir
    lengths = [len(folder) for folder in dirs]
    if len(set(lengths)) > 1:
        raise ValueError('More than one length of dirs in folder. Lengths: ' + str(lengths) + '. Folder: ' + str(sourceroot) + '.')

    # delete oldest if already at maxbackups
    if maxbackups is not None:
        if len(dirs) >= maxbackups:
            shutil.remove(sourceroot / dirs[0])

    shutil.make_archive(destroot / latestdir, 'zip', sourceroot, latestdir)


def regbackup_full():
    
    if os.path.isfile(__projectdir__ / Path('paths/backupzipfolder.txt')):
        with open(__projectdir__ / Path('paths/backupzipfolder.txt')) as f:
            backupzipfolder = f.read()
            if backupzipfolder[-1] == '\n':
                backupzipfolder = backupzipfolder[: -1]
            backupzipfolder = backupzipfolder.replace('~', os.path.expanduser('~'))
        if not os.path.isdir(backupzipfolder):
            raise ValueError('backupzipfolder does not exist. backupzipfolder: ' + str(backupzipfolder) + '.')
    else:
        backupzipfolder = None
    if backupzipfolder is not None:
        if not os.path.isdir(backupzipfolder):
            os.mkdir(backupzipfolder)
    
    # get relevant date base folder names:{{{
    now = datetime.datetime.now()
    
    adjusted = datetime.datetime(now.year, now.month, now.day, now.hour, (now.minute // 5) * 5)
    latest5mins = adjusted.strftime("%Y%m%d_%H%M")

    latesthour = now.strftime("%Y%m%d_%H00")
    latestday = now.strftime("%Y%m%d")

    if now.day <=10:
        adjustedday = 1
    elif now.day <=20:
        adjustedday = 11
    else:
        adjustedday = 21
    adjusted = datetime.datetime(now.year, now.month, adjustedday)
    latest10day = adjusted.strftime("%Y%m%d")
    # get relevant date base folder names:}}}

    # do backup for backupfiles:{{{
    backupfilesloc = Path(os.path.expanduser('~') + '/temp/regbackupfiles/')
    if not os.path.isdir(backupfilesloc):
        os.mkdir(backupfilesloc)
    # every 5 minutes
    fiveminsrootfiles = backupfilesloc / Path('5mins')
    if not os.path.isdir(fiveminsrootfiles):
        os.mkdir(fiveminsrootfiles)
    fiveminsdirfiles = fiveminsrootfiles / Path(latest5mins)
    if not os.path.isdir(fiveminsdirfiles):
        renameoldest(fiveminsrootfiles, latest5mins, 12)
        backupfiles(fiveminsdirfiles)
    # every 1 hour
    onehourrootfiles = backupfilesloc / Path('1hour')
    if not os.path.isdir(onehourrootfiles):
        os.mkdir(onehourrootfiles)
    onehourdirfiles = onehourrootfiles / Path(latesthour)
    if not os.path.isdir(onehourdirfiles):
        renameoldest(onehourrootfiles, latesthour, 24)
        backupfiles(onehourdirfiles)
    # every 1 day
    onedayrootfiles = backupfilesloc / Path('1day')
    if not os.path.isdir(onedayrootfiles):
        os.mkdir(onedayrootfiles)
    onedaydirfiles = onedayrootfiles / Path(latestday)
    if not os.path.isdir(onedaydirfiles):
        renameoldest(onedayrootfiles, latestday, 24)
        backupfiles(onedaydirfiles)
    # every 10 day
    tendaysrootfiles = backupfilesloc / Path('10days')
    if not os.path.isdir(tendaysrootfiles):
        os.mkdir(tendaysrootfiles)
    tendaysdirfiles = tendaysrootfiles / Path(latest10day)
    if not os.path.isdir(tendaysdirfiles):
        renameoldest(tendaysrootfiles, latest10day, 10)
        backupfiles(tendaysdirfiles)
    # make backupzipfolder for files
    if backupzipfolder is not None:
        if not os.path.isdir(backupzipfolder / Path('files')):
            os.mkdir(backupzipfolder / Path('files'))
        # every 1 day
        onedayziprootfiles = backupzipfolder / Path('files/1day')
        if not os.path.isdir(onedayziprootfiles):
            os.mkdir(onedayziprootfiles)
        copyziplatest(onedayrootfiles, onedayziprootfiles, maxbackups = 10)
        # every 10 day
        tendaysziprootfiles = backupzipfolder / Path('files/10days')
        if not os.path.isdir(tendaysziprootfiles):
            os.mkdir(tendaysziprootfiles)
        copyziplatest(tendaysrootfiles, tendaysziprootfiles, maxbackups = None)
    # do backup for backupfiles:}}}

    # do backup for backupfolders:{{{
    backupfoldersloc = Path(os.path.expanduser('~') + '/temp/regbackupfolders/')
    if not os.path.isdir(backupfoldersloc):
        os.mkdir(backupfoldersloc)
    # every 1 hour
    onehourrootfolders = backupfoldersloc / Path('1hour')
    if not os.path.isdir(onehourrootfolders):
        os.mkdir(onehourrootfolders)
    onehourdirfolders = onehourrootfolders / Path(latesthour)
    if not os.path.isdir(onehourdirfolders):
        renameoldest(onehourrootfolders, latesthour, 24)
        backupfolders(onehourdirfolders)
    # every 1 day
    onedayrootfolders = backupfoldersloc / Path('1day')
    if not os.path.isdir(onedayrootfolders):
        os.mkdir(onedayrootfolders)
    onedaydirfolders = onedayrootfolders / Path(latestday)
    if not os.path.isdir(onedaydirfolders):
        renameoldest(onedayrootfolders, latestday, 24)
        backupfolders(onedaydirfolders)
    # every 10 day
    tendaysrootfolders = backupfoldersloc / Path('10days')
    if not os.path.isdir(tendaysrootfolders):
        os.mkdir(tendaysrootfolders)
    tendaysdirfolders = tendaysrootfolders / Path(latest10day)
    if not os.path.isdir(tendaysdirfolders):
        renameoldest(tendaysrootfolders, latest10day, 10)
        backupfolders(tendaysdirfolders)
    # make backupzipfolder for files
    if backupzipfolder is not None:
        if not os.path.isdir(backupzipfolder / Path('folders')):
            os.mkdir(backupzipfolder / Path('folders'))
        # every 1 day
        onedayziprootfolders = backupzipfolder / Path('folders/1day')
        if not os.path.isdir(onedayziprootfolders):
            os.mkdir(onedayziprootfolders)
        copyziplatest(onedayrootfolders, onedayziprootfolders, maxbackups = 10)
        # every 10 days
        tendaysziprootfolders = backupzipfolder / Path('folders/10days')
        if not os.path.isdir(tendaysziprootfolders):
            os.mkdir(tendaysziprootfolders)
        copyziplatest(tendaysrootfolders, tendaysziprootfolders, maxbackups = None)
    # do backup for backupfolders:}}}


def checkworking():
    import datetime

    yesterday = datetime.date.today() - datetime.timedelta(1)
    filename = '~/temp/regbackupfolders/1day/'.replace('~', os.path.expanduser('~')) + str(yesterday.year)[0: 4] + str(yesterday.month).zfill(2) + str(yesterday.day).zfill(2)

    if not os.path.isdir(filename):
        sys.path.append(str(__projectdir__ / Path('submodules/linux-popupinfo/')))
        from displaypopup_func import genpopup
        genpopup('Regbackup did not back up daily yesterday', title = 'Regbackup')
        

# Run:{{{1
if __name__ == "__main__":
    regbackup_full()
