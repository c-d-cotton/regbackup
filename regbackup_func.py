#!/usr/bin/env python3
import datetime
import functools
import os
from pathlib import Path
import shutil
import subprocess
import sys

__projectdir__ = Path(os.path.dirname(os.path.realpath(__file__)) + '/')


sys.path.append(str(__projectdir__ / Path('submodules/allcode-list/')))
from getallcode_func import getallcode

# argparse fileinputs
sys.path.append(str(__projectdir__ / Path('submodules/argparse-fileinputs/')))
from argparse_fileinputs import add_fileinputs
from argparse_fileinputs import process_fileinputs

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
    
def rsyncfolders(folderstosync, rootbackupfolder, namesdict = None, excludefolders = None):
    """
    This document provides functions to do backups regularly
    I allow for different possible backups
    This function is one potential form of backup (that I use myself)
    """
    if namesdict is None:
        namesdict = {}
    if not os.path.isdir(rootbackupfolder):
        os.mkdir(rootbackupfolder)
    for folder in folderstosync:
        if folder not in namesdict:
            namesdict[folder] = os.path.basename(os.path.abspath(folder))

        # need to add separator on the end otherwise rsync doesn't work well
        sourcefolder = os.path.abspath(folder) + os.sep
        destfolder = os.path.join(rootbackupfolder, namesdict[folder]) + os.sep

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
    badfolders = [folder for folder in os.listdir(rootbackupfolder) if folder not in goodfolders]
    for folder in badfolders:
        folder2 = os.path.join(rootbackupfolder, folder)
        subprocess.call(['chmod', '-R', '777', folder2])
        shutil.rmtree(folder2)

    
# Auxilliary Regbackup Functions:{{{1
def runbackup_freqs_single(backupfunc, rootfolder, newdate, maxbackups):
    """
    Verifies that all files are same length as newdate as a basic check

    If newdate already exists in rootfolder then stop
    Otherwise:
    If rootfolder already contains files equivalent to maxbackups, rename the oldest as newdate
    Then run backupfunc on newdate
    """

    # rootfolder should be something like regbackup/M5/
    if not os.path.isdir(rootfolder):
        os.makedirs(rootfolder)

    dirs = os.listdir(rootfolder)
    dirs = sorted(dirs)

    # verify all zips have same length as latestdir
    lengths = [len(folder) for folder in dirs]
    if len(set(lengths)) > 1:
        raise ValueError('More than one length of dirs in folder. Lengths: ' + str(lengths) + '. Folder: ' + str(rootfolder) + '.')
    if len(lengths) == 1 and len(dirs[0]) != len(newdate):
        raise ValueError('newdate does not match dates in the existing folder. Current date format: ' + str(dirs[0]) + '. New date: ' + str(newdate) + '.')

    if newdate in dirs:
        # newdate already in dirs so backup already exists - can stop
        return(None)

    if len(dirs) >= maxbackups:
        shutil.move(rootfolder / Path(dirs[0]), rootfolder / Path(newdate))

    backupfunc(rootfolder / Path(newdate))

    
def runbackup_freqs(backupfunc, rootbackupfolder, freqs):
    """
    runs a backup function at specified frequencies and saves the different backups at rootbackupfolder

    backupfunc is a function that takes one argument, backupfolder, and creates/updates a backup located at backupfolder
    
    rootbackupfolder is the overall folder where the frequency backups will be saved
    freqs are the frequencies with which the backups should be saved
    Options for freqs: M5 (every 5 mins), H1 (every hour), d1 (every day), d10 (every 10 days), m1 (every 1 month)

    If H1 is specified in freqs, then a backup is created at rootbackupfolder/H1/yyyymmdd_HH

    A limited number of backups will be created i.e. 24 for H1, 12 for M5 etc.
    Once the limit is met, old backups will be updated rather than new ones created
    """

    # first create root backup path
    if not os.path.isdir(rootbackupfolder):
        os.makedirs(rootbackupfolder)

    # verify no weird terms included in freqs
    badterms = set(freqs) - {'M5', 'H1', 'd1', 'd10', 'm1'}
    if len(badterms) > 0:
        raise ValueError('Following bad terms in freqs: ' + str(badterms) + '.')

    # get relevant date base folder names:{{{
    now = datetime.datetime.now()
    
    H1_strf = now.strftime("%Y%m%d_%H")
    d1_strf = now.strftime("%Y%m%d")
    m1_strf = now.strftime("%Y%m")

    adjusted = datetime.datetime(now.year, now.month, now.day, now.hour, (now.minute // 5) * 5)
    M5_strf = adjusted.strftime("%Y%m%d_%H%M")

    if now.day <=10:
        adjustedday = 1
    elif now.day <=20:
        adjustedday = 11
    else:
        adjustedday = 21
    adjusted = datetime.datetime(now.year, now.month, adjustedday)
    d10_strf = adjusted.strftime("%Y%m%d")
    # get relevant date base folder names:}}}

    if 'M5' in freqs:
        runbackup_freqs_single(backupfunc, rootbackupfolder / Path('M5'), M5_strf, 12)
    if 'H1' in freqs:
        runbackup_freqs_single(backupfunc, rootbackupfolder / Path('H1'), H1_strf, 24)
    if 'd1' in freqs:
        runbackup_freqs_single(backupfunc, rootbackupfolder / Path('d1'), d1_strf, 12)
    if 'd10' in freqs:
        runbackup_freqs_single(backupfunc, rootbackupfolder / Path('d10'), d10_strf, 10)
    if 'm1' in freqs:
        runbackup_freqs_single(backupfunc, rootbackupfolder / Path('m1'), m1_strf, 13)
        

# Backup Code:{{{1
def backupcode_single(allcode, rootbackupfolder):
    """
    Back up only files marked as code - not whole folders
    """
    # remove common paths from allcode
    commonprefix = os.path.commonprefix(allcode)

    # get allcode without a prefix
    allcode_noprefix = [filename[len(commonprefix): ] for filename in allcode]

    # get list of files in current rootbackupfolder
    existingfiles = []
    existingdirs = []
    for root, dirs, files in os.walk(str(rootbackupfolder), topdown=False):
        for name in files:
            existingfiles.append(os.path.join(root, name))
        for name in dirs:
            existingdirs.append(os.path.join(root, name))

    # get existing files iwthout prefix
    existingfiles_noprefix = [filename[len(str(rootbackupfolder)) + 1: ] for filename in existingfiles]

    # add/update files in allcode
    for filename in allcode_noprefix:
        oldloc = os.path.join(commonprefix, filename)
        newloc = os.path.join(rootbackupfolder, filename)

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
            os.remove(os.path.join(rootbackupfolder, filename))

    # delete empty folders
    for existingdir in existingdirs:
        if len(os.listdir(existingdir)) == 0:
            # note this will only remove folders with no folders in
            # so would not remove dir1 if dir1/dir2 exists
            # but if dir2 contains no folders dir2 would be removed
            # then dir1 could be removed
            os.rmdir(existingdir)


def backupcode_single_test():
    # get files in this folder
    allcode = os.listdir(__projectdir__)
    allcode = [os.path.abspath(filename) for filename in allcode]
    allcode = [filename for filename in allcode if os.path.isfile(filename)]

    rootbackupfolder = '~/TEST_backupcode_single/'

    backupcode_single(allcode, rootbackupfolder)   


def backupcode_all(allcode, rootbackupfolder, freqs):
    rootbackupfolder = rootbackupfolder.replace('~', os.path.expanduser('~'))

    backupcode_aux = functools.partial(backupcode_single, allcode)
    runbackup_freqs(backupcode_aux, rootbackupfolder, freqs)
    

def backupcode_all_test():
    # get files in this folder
    allcode = os.listdir(__projectdir__)
    allcode = [os.path.abspath(filename) for filename in allcode]
    allcode = [filename for filename in allcode if os.path.isfile(filename)]

    rootbackupfolder = '~/TEST_backupcode_all/'

    freqs = ['M5', 'H1', 'd1', 'd10', 'm1']

    backupcode_all(allcode, rootbackupfolder, freqs) 


def backupcode_all_ap():
    #Argparse:{{{
    import argparse
    
    parser=argparse.ArgumentParser()

    # add input for files
    parser.add_argument("rootbackupfolder", help = "where backup should be saved")
    parser = add_fileinputs(parser)
    parser.add_argument('-f', '--freq', action = 'append', help = 'Input list of frequencies with which backup should occur. Should be at least one of M5, H1, d1, d10, m1.')
    
    args=parser.parse_args()
    #End argparse:}}}

    allcode = process_fileinputs(args)

    backupcode_all(allcode, args.rootbackupfolder, args.freq)


# Backup Dirs:{{{1
def backupdirs_single(alldirs, rootbackupfolder, excludestandard = True):
    """
    Back up whole folders in my code but ignoring a few very specific folders
    """
    folderstosync = [p for p in alldirs if not p.startswith('#')]
    folderstosync = [p.replace('~', os.path.expanduser('~')) for p in folderstosync]

    # need ** to cover submodules/ and folder/submodules/
    # * only covers folder/submodules/ but not submodules/
    rsyncfolders(folderstosync, rootbackupfolder, excludefolders = ['**/submodules/', '**/submodules/', '**/*-external'])


def backupdirs_single_test():
    alldirs = [str(__projectdir__)]

    rootbackupfolder = '~/TEST_backupdirs/'

    backupdirs(alldirs, rootbackupfolder)


def backupdirs_all(alldirs, rootbackupfolder, freqs, excludestandard = True):
    rootbackupfolder = rootbackupfolder.replace('~', os.path.expanduser('~'))
    
    backupdirs_aux = functools.partial(backupdirs_single, alldirs, excludestandard = True)
    runbackup_freqs(backupdirs_aux, rootbackupfolder, freqs)
    

def backupdirs_all_test():
    # get files in this folder
    alldirs = [str(__projectdir__)]

    rootbackupfolder = '~/TEST_backupdirs_all/'

    freqs = ['M5', 'H1', 'd1', 'd10', 'm1']

    backupdirs_all(alldirs, rootbackupfolder, freqs) 


def backupdirs_all_ap():
    #Argparse:{{{
    import argparse
    
    parser=argparse.ArgumentParser()

    # add input for files
    parser.add_argument("rootbackupfolder", help = "where backup should be saved")
    parser = add_fileinputs(parser)
    parser.add_argument('-f', '--freq', action = 'append', help = 'Input list of frequencies with which backup should occur. Should be at least one of M5, H1, d1, d10, m1.')
    parser.add_argument("--includeallsubfolders", action = 'store_true')
    
    args=parser.parse_args()
    #End argparse:}}}

    alldirs = process_fileinputs(args)

    backupdirs_all(alldirs, args.rootbackupfolder, args.freq, excludestandard = not args.includeallsubfolders)


# Zip:{{{1
def copyziplatest(sourceroot, destroot, maxbackups = None):
    """
    Used when copying over the latest unzipped version of a folder to a new zipped version in a different folder

    If folder already contains files equivalent to maxbackups, delete the oldest
    Also verifies that all files are same length as newdate as a basic check
    """
    # replace ~
    sourceroot = sourceroot.replace('~', os.path.expanduser('~'))
    destroot = destroot.replace('~', os.path.expanduser('~'))

    sourceroot = Path(sourceroot)
    destroot = Path(destroot)

    if not os.path.isdir(destroot):
        os.makedirs(destroot)
    if not os.path.isdir(sourceroot):
        raise ValueError('sourceroot is not a folder: ' + str(sourceroot) + '.')

    dirs = os.listdir(sourceroot)
    if len(dirs) == 0:
        raise ValueError('No folders in sourceroot: ' + str(sourceroot) + '.')

    dirs = sorted(dirs)
    latestdir = dirs[-1]

    # verify all zips have same length as latestdir
    lengths = [len(folder) for folder in dirs]
    if len(set(lengths)) > 1:
        raise ValueError('More than one length of dirs in folder. Lengths: ' + str(lengths) + '. Folder: ' + str(sourceroot) + '.')

    # stop if already exists
    if os.path.exists(destroot / Path(latestdir + ".zip")):
        return(None)

    # delete oldest if already at maxbackups
    if maxbackups is not None:
        if len(dirs) >= maxbackups:
            shutil.remove(sourceroot / dirs[0])

    shutil.make_archive(destroot / latestdir, 'zip', sourceroot, latestdir)


def copyziplatest_test():
    # run backupdirs_all_test() first so have folder to zip up
    backupdirs_all_test()

    copyziplatest('~/TEST_backupdirs_all/M5/', '~/TEST_backupdirs_all/M5zip/')


def copyziplatest_ap():
    """
    Used when copying over the latest unzipped version of a folder to a new zipped version in a different folder

    If folder already contains files equivalent to maxbackups, delete the oldest
    Also verifies that all files are same length as newdate as a basic check
    """

    #Argparse:{{{
    import argparse
    
    parser=argparse.ArgumentParser()
    parser.add_argument("sourceroot", help = "the folder where the latest folder is copied from i.e. regbackup/code/M5/")
    parser.add_argument("destroot", help = "the folder where the zip will be created")
    parser.add_argument("--maxbackups", type = int, help = "the maximum number of backups. Once this is reached, old backups are deleted when new ones are created.")
    
    args=parser.parse_args()
    #End argparse:}}}

    copyziplatest(args.sourceroot, args.destroot, maxbackups = args.maxbackups)


# Other Functions:{{{1
def checkworking():
    import datetime

    yesterday = datetime.date.today() - datetime.timedelta(1)
    filename = '~/temp/regbackup/dirs/d1/'.replace('~', os.path.expanduser('~')) + str(yesterday.year)[0: 4] + str(yesterday.month).zfill(2) + str(yesterday.day).zfill(2)

    if not os.path.isdir(filename):
        sys.path.append(str(__projectdir__ / Path('submodules/linux-popupinfo/')))
        from displaypopup_func import genpopup
        genpopup('Regbackup did not back up daily yesterday', title = 'Regbackup')
        

