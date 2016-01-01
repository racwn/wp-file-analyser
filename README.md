# wp-file-analyser
Find modified, missing and extra files in a WordPress directory.

# Usage
```shell
$ ./analyser.py -v path-to-wordpress-directory

                  ___ _ _                            _
                 / __|_) |                          | |
  _ _ _ ____    | |__ _| | ____     ____ ____   ____| |_   _  ___  ____  ____
 | | | |  _ \   |  __) | |/ _  )   / _  |  _ \ / _  | | | | |/___)/ _  )/ ___)
 | | | | | | |  | |  | | ( (/ /   ( ( | | | | ( ( | | | |_| |___ ( (/ /| |
  \____| ||_/   |_|  |_|_|\____)   \_||_|_| |_|\_||_|_|\__  (___/ \____)_|
       |_|                                            (____/
    
Setting up:
Downloading a new copy of WordPress
wordpress_4.4.zip [==================================================]
Getting plugins:
akismet.3.1.5.zip [==================================================]
wp-super-cache.1.4.7.zip [==================================================]
Comparing wordpress/ with wpa-temp/wordpress/
Starting Analysis:
DIFF: (3)
wordpress/wp-content/themes/index.php
wordpress/wp-blog-header.php
wordpress/wp-content/plugins/wp-super-cache/ossdl-cdn.php
EXTRA: (2)
wordpress/wp-config.php
wordpress/wp-admin/bad.php
MISSING: (2)
wpa-temp/wordpress/wp-content/plugins/akismet/class.akismet.php
wpa-temp/wordpress/wp-admin/css/about.css
PHP FILES IN 'WP-CONTENT/UPLOADS': (1)
wordpress/wp-content/uploads/bad.php
```

# About
When fixing hacked Wordpress sites I needed a way of quickly comparing the core and plugin files against their wordpress.org originals. This python script automates the process of downloading the same copy of WordPress and plugins into a new directory and then comparing the two.

When run the script will create a temporary directory called ‘wpa-temp’. It will then download a new copy of the same version of WordPress into that directory, along with any plugins that are hosted on wordpress.org. The two directories are then compared and the following displayed:
- DIFF - files that are in both, but have been modified in the original.  
- EXTRA - files that are in the old copy, but not in the new.  
- MISSING - files that are in the new copy, but not in the old.  
- PHP IN UPLOADS - and .php files that are in the wp-content/uploads directory.  

If using this script to repair a WordPress site please note the following: 
- Do not delete all files reported as EXTRA, Some plugins during installation add files outside of their plugin directory which will be picked up. wp-config.php will also be listed. 
- Be aware that a developer may of (against best practice) modified core and plugin files. Review them before overwriting with the originals.  
- In most cases the theme files are not scanned. Ensure these are reviewed manually before declaring the site free of malware. 
- Premium themes and plugins cannot be auto downloaded. Run the tool to create the wpa-temp directory, then manually copy these required files in. Finally re-run the tool and pass the wpa-temp directory as the second argument.  


# Installation
Download analyser.py to your required directory (directory above your WordPress install makes sense). Make executable with:
```shell
chmod +x analyser.py
```

# Requirments
requests - http://docs.python-requests.org/en/latest/

# Command line options
Show help
```shell
./analyser.py -h
```
Verbose mode - shows info messages and download progress bars 
```shell
./analyser.py -v wordpress-path/
```
Compare against another existing WordPress directory 
```shell
./analyser.py -v wordpress-path/ other-wordpress-path/
```
Compare against an certain version, e.g. WordPress 4.4
```shell
./analyser.py -v -w 4.4 wordpress-path/
```
Delete temporary files. During analysis a directory called wpa-temp is created that holds the new copies of files, delete this after running. 
```shell
./analyser.py -t wordpress-path/
```

# Tests
Requires nose, run the following from the top level of the project directory
```shell
nosetests
```

# License
Licensed under GPLv3 