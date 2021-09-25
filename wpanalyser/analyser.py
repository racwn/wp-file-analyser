#!/usr/bin/env python

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from filecmp import dircmp
from typing import Any, Literal, Tuple, Iterable, IO, TextIO, BinaryIO, overload

import requests
from requests.exceptions import HTTPError

# File that contains the WordPress version number
WP_VERSION_FILE_PATH = "wp-includes/version.php"

# To get a particular version, add its number + .zip, e.g 4.2.1.zip
WP_PACKAGE_ARCHIVE_LINK = "https://wordpress.org/wordpress-"

# To get a plugin add name (words separated by -) + version, e.g.
# photo-gallery.1.4.3.zip
WP_PLUGIN_ARCHIVE_LINK = "https://downloads.wordpress.org/plugin/"

# Url for standard wordpress themes, add theme + version num
# e.g. appointment.2.4.5.zip
WP_THEME_ARCHIVE_LINK = "https://downloads.wordpress.org/theme/"

# Ignore everything below these directories
IGNORED_WP_DIRS = ['wp-content/themes', 'wp-content/uploads']

# Some common files to search for when identifying a WordPress directory
WP_COMMON_FILES = ['wp-login.php', 'wp-blog-header.php',
                   'wp-admin/admin-ajax.php', 'wp-includes/version.php']

# File extensions that may be executed by php processor
PHP_FILE_EXTENSIONS = ('.php', '.phtml', '.php3', '.php4', '.php5', '.phps')

# Directory to hold downloaded files
TEMP_DIR = 'wpa-temp'

# Should info messages be displayed
verbose = False


def msg(message: str, error: bool = False) -> None:
    """Print a message according to verbosity and error conditions."""
    if error or verbose:
        print(message)


@overload
def open_file(fileName: str, mode: Literal['r', 'w']) -> TextIO|Literal[False]: ...
@overload
def open_file(fileName: str, mode: Literal['rb', 'wb']) -> BinaryIO|Literal[False]: ...
def open_file(fileName: str, mode: str) -> IO[Any]|Literal[False]:
    """Open file with mode. Return False on failure."""
    try:
        return open(fileName, mode)
    except IOError as e:
        msg("Error opening [%s]: %s" % (fileName, e.strerror), True)
        return False


def unzip(zippedFile: str, outPath: str) -> str | Literal[False]:
    """Extract all files from a zip archive to a destination directory."""
    fh = open_file(zippedFile, 'rb')
    if not fh:
        return False
    with fh:
        try:
            z = zipfile.ZipFile(fh)
            namelist = z.namelist()
            newDir = namelist[0]  # the toplevel directory name in the zipfile
            for name in namelist:
                z.extract(name, outPath)
            return newDir
        except RuntimeError as re:
            msg("Error processing zip (RuntimeError): %s" % re, True)
            return False
        except IOError as ioe:
            msg("Error opening [%s]: %s" % (zippedFile, ioe.strerror), True)
            return False
        except zipfile.BadZipfile as bzf:
            msg("Bad zip file: %s" % zippedFile, True)
            return False


def download_file(fileUrl: str, newFilePath: str, newFileName: str) -> bool:
    """Download a file via HTTP. If verbose is true, show a progress bar"""
    newFile = os.path.join(newFilePath, newFileName)
    if os.path.isfile(newFile):
        msg("ERROR: cannot download %s, file already exists" % newFile, True)
        return False
    response = requests.get(fileUrl, stream=True)
    try:
        response.raise_for_status()
    except HTTPError:
        msg("ERROR: download problem[%s]: %s " % (response.status_code, fileUrl), True)
        return False
    else:
        f = open_file(newFile, "wb")
        if not f:
            msg("ERROR: cannot create new file %s" % newFile, True)
            return False
        with f:
            contentLengthHeader = response.headers.get('content-length')
            if (contentLengthHeader is None) or (verbose is False):
                f.write(response.content)
            else:
                dl = 0
                contentLength = int(contentLengthHeader)
                sys.stdout.write("\r%s [%s]" % (newFileName, ' ' * 50))
                for data in response.iter_content(chunk_size=1024):
                    if data:
                        dl += len(data)
                        f.write(data)
                        done = int(50 * dl / contentLength)
                        sys.stdout.flush()
                        sys.stdout.write("\r%s [%s%s]" % (
                                                         newFileName,
                                                         '=' * done,
                                                         ' ' * (50-done)))
                print()  # newline after progress bar
        return True


def search_dir_for_exts(searchDir: str, exts: Tuple[str, ...]) -> set[str]:
    """Search directory and its sub-directories for files with extensions."""
    foundFiles = set()
    for root, dirs, files in os.walk(searchDir):
        for f in files:
            if f.endswith(exts):
                foundFiles.add(os.path.join(root, f))
    return foundFiles


def is_subdir(child: str, parent: str) -> bool:
    """Return True if child is a sub-directory of parent directory."""
    absPath = os.path.abspath(child)
    absDir = os.path.abspath(parent)
    return absPath.startswith(absDir + os.path.sep)


def ignored_file(f: str, wpPath: str) -> bool:
    """Returns True if a file should be ignored."""
    for s in IGNORED_WP_DIRS:
        if s in f:  # test if partial path string in IGNORED_WP_DIRS
            if is_subdir(f, os.path.join(wpPath, s)):
                return True
    return False


def search_file_for_string(searchFile: str, string: str) -> str|Literal[False]:
    """Search file for the first line that contains string and return it"""
    f = open_file(searchFile, 'r')
    if not f:
        return False
    with f:
        for i, line in enumerate(f):
            if string in line:
                return line
        return False


def find_plugin_details(readmePath: str) -> Tuple[str, str|Literal[False]]:
    """Search file for 'Stable tag: ' and copy return the version number
    after it. Extract the plugin name from the file path.
    """
    version: str|Literal[False]
    versionLine = search_file_for_string(readmePath, "Stable tag:")
    if versionLine:
        cutStart = versionLine.find(':') + 2
        version = versionLine[cutStart:-1]
    else:
        version = False
    nameCutStart =  readmePath.find('plugins')
    nameCutStart = nameCutStart + 8
    nameCutEnd = readmePath.find(os.path.sep, nameCutStart)
    name = readmePath[nameCutStart:nameCutEnd]
    return name, version


def find_wp_version(versionFile: str) -> str|Literal[False]:
    """Search file for the string "$wp_version =" and return the version number 
    after it.
    """
    line = search_file_for_string(versionFile, "$wp_version =")
    if not line:
        return False
    else:
        cutStart = line.find("'") + 1
        cutEnd = line.find("'", cutStart + 1)
        if (cutStart <= 0) or (cutEnd <= cutStart):
            return False
        else:
            return line[cutStart:cutEnd]


def find_theme_details(stylesheet: str) -> Tuple[str|Literal[False], str|Literal[False]]:
    """Extract the theme name and version from theme stylesheet"""
    nameLine = search_file_for_string(stylesheet, "Text Domain:")
    name: str|Literal[False] = nameLine[nameLine.find(':') + 2:-1] if nameLine else False
    versionLine = search_file_for_string(stylesheet, "Version:")
    version: str|Literal[False] = versionLine[versionLine.find(':') + 2:-1] if versionLine else False
    return name, version


def download_wordpress(version: str, toDir: str) -> Tuple[bool, str]:
    """Download the identified WordPress archive version into toDir."""
    newFileName = "wordpress_%s.zip" % version
    fileUrl = "%s%s.zip" % (WP_PACKAGE_ARCHIVE_LINK, version)
    res = download_file(fileUrl, toDir, newFileName)
    newFilePath = os.path.join(toDir, newFileName)
    return res, newFilePath

def get_zipped_asset(zipUrl: str, zipName: str, toPath: str) -> str|Literal[False]:
    """Download zip file as zipName from URL and extract it toPath"""
    res = download_file(zipUrl, TEMP_DIR, zipName)
    if not res:
        return False
    zipFilePath = os.path.join(TEMP_DIR, zipName)
    extractPath = unzip(zipFilePath, toPath)
    os.remove(zipFilePath)
    return extractPath


def get_plugin(name: str, version: str, wpDir: str) -> str | Literal[False]:
    """Get a new copy of given plugin version, extract it to the plugins directory of wpDir"""
    zipName = "%s.%s.zip" % (name, version)
    zipUrl = "%s%s" % (WP_PLUGIN_ARCHIVE_LINK, zipName)
    toPath = os.path.join(wpDir, 'wp-content', 'plugins')
    extractPath = get_zipped_asset(zipUrl, zipName, toPath)
    return extractPath


def get_theme(name: str, version: str, wpDir: str) -> str | Literal[False]:
    """Get a new copy of given theme version, extract it to the themes directory of wpDir"""
    zipName = "%s.%s.zip" % (name, version)
    zipUrl = "%s%s" % (WP_THEME_ARCHIVE_LINK, zipName)
    toPath = os.path.join(wpDir, 'wp-content', 'themes')
    extractPath = get_zipped_asset(zipUrl, zipName, toPath)
    return extractPath


def is_wordpress(dirPath: str) -> bool:
    """Return True if dirPath contains all the files in WP_COMMON_FILES."""
    for wpFile in WP_COMMON_FILES:
        if not os.path.isfile(os.path.join(dirPath, wpFile)):
            return False
    return True


def get_file_from_each_subdirectory(path: str, fileName: str) -> Iterable[str]:
    """For each subdirectory of path, return a path of fileName if found"""
    subdirs = next(os.walk(path))[1]  # get only the first level subdirs
    for d in subdirs:
        f = os.path.join(path, d, fileName)
        if os.path.isfile(f):
            yield f


def find_plugins(wpPath: str) -> Iterable[Tuple[str, str]]:
    """Return a list of plugins and their current versions"""
    pluginsDir = os.path.join(wpPath, 'wp-content', 'plugins')
    readmeFiles = get_file_from_each_subdirectory(pluginsDir, 'readme.txt')
    for readme in readmeFiles:
        name, version = find_plugin_details(readme)
        if not version:
            msg("ERROR: Could not find plugin version in %s" % readme)
            continue
        yield name, version


def find_themes(wpPath: str) -> Iterable[Tuple[str, str]]:
    """Return a list of themes and their versions"""
    themesDir = os.path.join(wpPath, 'wp-content', 'themes')
    themeStylesheets = get_file_from_each_subdirectory(themesDir, 'style.css')
    for stylesheet in themeStylesheets:
        name, version = find_theme_details(stylesheet)
        if not name:
            msg("ERROR: Could not find theme name in %s" % stylesheet)
            continue
        if not version:
            msg("ERROR: Could not find theme version in %s" % stylesheet)
            continue
        yield name, version


def analyze(dcres: dircmp[str], wpPath: str) -> Tuple[set[str], set[str], set[str]]:
    """Get extra, changed and missing files from a dircmp results object.

    From dircmp results find:
        1. Any files that differ.
        2. Extra files in left that are not in right.
        3. Missing files that are in right but not in left.
    Recursively enter sub directories to continue search.

    When searching for extra files, certain files and directories that are
    user modifiable should be ignored. For example, 'wp-content/themes' will
    likely contain unique files that will not appear in a new copy of the
    same WordPress version. These should be ignored to avoid giving false
    positives.
    """

    diff = set()
    extra = set()
    missing = set()

    # 1. Get modified files
    for f in dcres.diff_files:
        diff.add(os.path.join(dcres.left, f))

    # 2. Get extra files
    for name in dcres.left_only:
        path = os.path.join(dcres.left, name)
        if not ignored_file(path, wpPath):  # ignore user modified
            if not os.path.isdir(path):  # do not add directories
                extra.add(path)

    # 3. Get missing files
    for f in dcres.right_only:
        missing.add(os.path.join(dcres.right, f))

    # Recurse into each sub dir
    for sub_dcres in dcres.subdirs.values():
        newDiff, newExtra, newMissing = analyze(sub_dcres, wpPath)
        diff = diff.union(newDiff)
        extra = extra.union(newExtra)
        missing = missing.union(newMissing)

    return diff, extra, missing


def print_analysis(diff: set[str], extra: set[str], missing: set[str], extraPHP: set[str]) -> None:
    """Show file lists in an easy to copy format"""
    print("DIFF: (%s)" % len(diff))
    for f in diff:
        print(f)

    print("EXTRA: (%s)" % len(extra))
    for f in extra:
        print(f)

    print("MISSING: (%s)" % len(missing))
    for f in missing:
        print(f)

    print("PHP FILES IN 'WP-CONTENT/UPLOADS': (%s)" % len(extraPHP))
    for f in extraPHP:
        print(f)


def create_args() -> argparse.ArgumentParser:
    """Setup and return argparse object with required settings."""

    parser = argparse.ArgumentParser(description="""Find modified, missing
        or extra files in a Wordpress directory""")

    parser.add_argument('wordpress_path',
                        help="Path to WordPress directory to be analysed")

    parser.add_argument('-t', '--tidy-up', dest='remove_temporary_files',
                        action='store_true',
                        help="""Remove the downloaded copy of WordPress
                        and plugins after analysis""")

    parser.add_argument('-v', '--verbose', dest='verbose',
                        action='store_true',
                        help="""Display info messages""")

    group = parser.add_mutually_exclusive_group()

    group.add_argument('-w', '--with-version', help="""Compare WordPress files
        against specific version, do not auto-detect from existing files""")

    group.add_argument(
                        'other_wordpress_path',
                        nargs='?',
                        help="""Optionally compare against other WordPress
                        directory, do not download new version""")
    return parser


def process_wp_dirs(args: argparse.Namespace) -> Tuple[str|Literal[False], str|Literal[False]]:
    """Return paths to each WP directory, creating a new one where required."""

    wpPath: str = args.wordpress_path
    otherWpPath: str|Literal[False] = False

    isWordpress = is_wordpress(wpPath)
    if not isWordpress:
        print("ERROR: Could not find WordPress in %s" % wpPath)
        return False, False

    # If given a second directory check it contains a copy of WordPress
    other_wordpress_path: Optional[str] = args.other_wordpress_path
    if other_wordpress_path is not None:
        if is_wordpress(other_wordpress_path):
            otherWpPath = other_wordpress_path
        else:
            print("ERROR: Could not find Wordpress in %s" % otherWpPath)

    # Or download a new copy.
    else:
        msg('Downloading a new copy of WordPress')
        if not os.path.exists(TEMP_DIR):
            try:
                os.makedirs(TEMP_DIR)
            except OSError as e:
                msg("ERROR: Could not create temporary directory", True)
                return wpPath, False

        if args.with_version:  # If given a version use that
            version = args.with_version
        else:  # Otherwise auto-detect
            verF = os.path.join(wpPath, WP_VERSION_FILE_PATH)
            version = find_wp_version(verF)
            if not version:
                msg("ERROR: Could not detect version in %s" % verF, True)
                return wpPath, False

        res, zipFilePath = download_wordpress(version, TEMP_DIR)
        if not res:
            return wpPath, False
        else:
            extractedPath = unzip(zipFilePath, TEMP_DIR)
            if not extractedPath:
                return wpPath, False
            else:
                otherWpPath = os.path.join(TEMP_DIR, extractedPath)

    return wpPath, otherWpPath


def main() -> None:

    parser = create_args()
    args = parser.parse_args()

    global verbose
    verbose = args.verbose

    msg("""
                  ___ _ _                            _
                 / __|_) |                          | |
  _ _ _ ____    | |__ _| | ____     ____ ____   ____| |_   _  ___  ____  ____
 | | | |  _ \   |  __) | |/ _  )   / _  |  _ \ / _  | | | | |/___)/ _  )/ ___)
 | | | | | | |  | |  | | ( (/ /   ( ( | | | | ( ( | | | |_| |___ ( (/ /| |
  \____| ||_/   |_|  |_|_|\____)   \_||_|_| |_|\_||_|_|\__  (___/ \____)_|
       |_|                                            (____/
    """)

    msg('Setting up:')

    wpPath, otherWpPath = process_wp_dirs(args)
    if (wpPath is False) or (otherWpPath is False):
        msg('ERROR: could not get WordPress directories for comparison', True)
        sys.exit()

    # Get plugins and themes, but only when a new WordPress directory has 
    # been created.
    if not args.other_wordpress_path:
        msg('Getting plugins:')
        for name, version in find_plugins(wpPath):
            res = get_plugin(name, version, otherWpPath)
            if not res:
                msg("ERROR: Could not download %s %s" % (name, version), True)

        msg('Getting themes:')
        for name, version in find_themes(wpPath):
            res = get_theme(name, version, otherWpPath)
            if not res:
                msg("ERROR: Could not download %s %s" % (name, version), True)

    msg('Comparing %s with %s' % (wpPath, otherWpPath))

    msg('Starting Analysis:')
    dcres = dircmp(wpPath, otherWpPath)
    diff, extra, missing = analyze(dcres, wpPath)

    uploadsPath = os.path.join(wpPath, 'wp-content', 'uploads')
    phpFiles = search_dir_for_exts(uploadsPath, PHP_FILE_EXTENSIONS)

    print_analysis(diff, extra, missing, phpFiles)

    if args.remove_temporary_files:
        if os.path.exists(TEMP_DIR):
            msg("Removing %s " % TEMP_DIR)
            shutil.rmtree(TEMP_DIR)

if __name__ == "__main__":
    main()
