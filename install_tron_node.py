#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time
import shutil
import requests
import tarfile
import stat
import re
import logging
import json
from datetime import datetime
import traceback
import atexit
import argparse

# Get absolute path of the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if not SCRIPT_DIR:
    SCRIPT_DIR = os.getcwd()
LOG_DIR = SCRIPT_DIR
LOG_FILE = f"{LOG_DIR}/installation.log"

# Create log directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)
print(f"Log directory: {LOG_DIR}")

# Configure logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Get logger
logger = logging.getLogger('tron_installer')

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Main paths
HOME_DIR = os.path.expanduser("~")
TRON_DIR = "/home/java-tron"
OUTPUT_DIR = f"{TRON_DIR}/output-directory"
CONFIG_FILE = f"{TRON_DIR}/last-conf.conf"
START_SCRIPT = f"{TRON_DIR}/last-node-start.sh"
SYSTEMD_SERVICE = "/etc/systemd/system/tron-node.service"
VSCODE_SETTINGS_DIR = f"{TRON_DIR}/.vscode"
VSCODE_SETTINGS_FILE = f"{VSCODE_SETTINGS_DIR}/settings.json"

# Base URL for downloading archive (actual link will be determined automatically)
BASE_URL = "http://34.86.86.229/"

# Files to clean up after installation
CLEANUP_FILES = [
    f"{SCRIPT_DIR}/install_tron_node.py",
    f"{SCRIPT_DIR}/installation.log"
]
for i in range(10):
    CLEANUP_FILES.append(f"{LOG_DIR}/command_*.log")

def print_step(message):
    """Print installation step."""
    logger.info(message)
    print(f"\n{BLUE}==>{RESET} {message}")

def print_success(message):
    """Print success message."""
    logger.info(f"SUCCESS: {message}")
    print(f"{GREEN}✓ {message}{RESET}")

def print_error(message):
    """Print error message."""
    logger.error(f"ERROR: {message}")
    print(f"{RED}✗ ERROR: {message}{RESET}")
    
def print_warning(message):
    """Print warning message."""
    logger.warning(f"WARNING: {message}")
    print(f"{YELLOW}! {message}{RESET}")

def print_debug(message):
    """Print debug information."""
    logger.debug(message)

def run_command(command, check=True, shell=False, cwd=None, log_output=True):
    """Run command with output result and detailed logging."""
    logger.debug(f"Running command: {command}")
    
    # Create a file for command output logging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    command_log_file = f"{LOG_DIR}/command_{timestamp}.log"
    
    try:
        if isinstance(command, str) and not shell:
            command = command.split()
        
        # Run process with output capture for logging
        with open(command_log_file, 'w') as log_file:
            if log_output:
                process = subprocess.Popen(
                    command, 
                    cwd=cwd,
                    shell=shell, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                stdout_data = ""
                stderr_data = ""
                
                # Process stdout
                for line in process.stdout:
                    stdout_data += line
                    log_file.write(line)
                    log_file.flush()
                    logger.debug(f"STDOUT: {line.strip()}")
                
                process.stdout.close()
                
                # Process stderr
                for line in process.stderr:
                    stderr_data += line
                    log_file.write(f"ERROR: {line}")
                    log_file.flush()
                    logger.debug(f"STDERR: {line.strip()}")
                
                process.stderr.close()
                
                # Wait for process to complete
                returncode = process.wait()
                
                if check and returncode != 0:
                    logger.error(f"Command failed with return code {returncode}")
                    logger.error(f"Command stderr: {stderr_data}")
                    print_error(f"Command failed with return code {returncode}")
                    print(f"Stderr: {stderr_data}")
                    print(f"Full command log: {command_log_file}")
                    if check:
                        sys.exit(1)
                    return None
                
                logger.debug(f"Command completed successfully with return code {returncode}")
                return stdout_data.strip()
            else:
                # Run without output capture for interactive commands
                result = subprocess.run(
                    command, 
                    cwd=cwd,
                    check=check, 
                    shell=shell, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                # Log result
                log_file.write(f"STDOUT: {result.stdout}\n")
                log_file.write(f"STDERR: {result.stderr}\n")
                
                logger.debug(f"Command stdout: {result.stdout}")
                logger.debug(f"Command stderr: {result.stderr}")
                
                return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution error: {command}")
        logger.error(f"Stderr: {e.stderr}")
        print_error(f"Command execution error: {command}")
        print(f"Stderr: {e.stderr}")
        print(f"Full command log: {command_log_file}")
        if check:
            sys.exit(1)
        return None
    except Exception as e:
        logger.error(f"Unexpected error executing command: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Unexpected error executing command: {str(e)}")
        if check:
            sys.exit(1)
        return None

def run_command_with_live_output(command, cwd=None, shell=True):
    """Run command with real-time output display."""
    logger.debug(f"Running command with live output: {command}")
    
    # Create a file for command output logging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    command_log_file = f"{LOG_DIR}/command_live_{timestamp}.log"
    logger.info(f"Command log will be saved to: {command_log_file}")
    print(f"Command log will be saved to: {command_log_file}")
    
    try:
        with open(command_log_file, 'w') as log_file:
            process = subprocess.Popen(
                command, 
                cwd=cwd,
                shell=shell, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Read output and display in real-time
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    print(f"  | {line}")
                    log_file.write(f"{line}\n")
                    log_file.flush()
                    logger.debug(f"LIVE OUTPUT: {line}")
            
            # Get return code
            return_code = process.wait()
            logger.debug(f"Command completed with return code {return_code}")
            
            return return_code, command_log_file
    except Exception as e:
        logger.error(f"Error running command with live output: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error running command: {str(e)}")
        return 1, command_log_file

def check_root():
    """Check for root privileges."""
    logger.debug("Checking for root privileges")
    if os.geteuid() != 0:
        logger.error("Script requires root privileges")
        print_error("This script requires root privileges (sudo).")
        sys.exit(1)
    logger.debug("Root privileges confirmed")

def install_dependencies():
    """Install necessary dependencies."""
    print_step("Installing necessary packages...")
    logger.debug("Starting dependency installation")
    
    try:
        # Update package lists
        logger.debug("Updating package lists")
        run_command("apt update")
        
        # Install required packages
        logger.debug("Installing required packages")
        run_command("apt install -y git wget curl openjdk-8-jdk maven")
        
        # Check installation
        for package in ["git", "wget", "curl", "java"]:
            version_cmd = f"{package} --version"
            if package == "java":
                version_cmd = "java -version"
            
            try:
                version = run_command(version_cmd, check=False, shell=True)
                logger.debug(f"{package} version: {version}")
            except Exception as e:
                logger.warning(f"Could not get {package} version: {str(e)}")
        
        print_success("Packages installed")
        logger.debug("Dependencies installed successfully")
    
    except Exception as e:
        logger.error(f"Failed to install dependencies: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Failed to install dependencies: {str(e)}")
        sys.exit(1)

def configure_java():
    """Configure Java 8 as the main version."""
    print_step("Configuring Java 8...")
    logger.debug("Starting Java 8 configuration")
    
    # Force set JAVA_HOME environment variable
    java_home = "/usr/lib/jvm/java-8-openjdk-amd64"
    os.environ["JAVA_HOME"] = java_home
    logger.debug(f"Set JAVA_HOME={java_home}")
    
    # Export JAVA_HOME globally
    with open("/etc/profile.d/java.sh", "w") as f:
        f.write(f'export JAVA_HOME="{java_home}"\n')
        f.write('export PATH="$JAVA_HOME/bin:$PATH"\n')
    logger.debug("Added JAVA_HOME to /etc/profile.d/java.sh")
    
    # Source the file to apply changes
    run_command("source /etc/profile.d/java.sh", shell=True, check=False)
    
    # Direct approach with update-alternatives
    try:
        # Set Java 8 as default
        run_command("update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java", check=False)
        run_command("update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac", check=False)
        logger.debug("Set Java 8 as default using update-alternatives")
        
        # Verify Java 8 is set as default
        java_version = run_command("java -version 2>&1", check=False, shell=True)
        logger.debug(f"Java version: {java_version}")
        
        if "1.8" in java_version:
            print_success("Java 8 configured as main version")
        else:
            print_warning("Java 8 is not set as the main version, continuing anyway")
        
    except Exception as e:
        logger.error(f"Error configuring Java 8: {str(e)}")
        logger.error(traceback.format_exc())
        print_warning(f"Error configuring Java 8: {str(e)}")
        print_warning("Continuing anyway, but the build might fail")

def find_latest_backup_url():
    """Find URL of the latest available backup."""
    ARCHIVE_NAME = "LiteFullNode_output-directory.tgz"
    
    print_step("Searching for the latest available backup...")
    logger.debug(f"Searching for latest backup at {BASE_URL}")
    
    try:
        # Get page content
        logger.debug("Fetching base URL content")
        response = requests.get(BASE_URL)
        response.raise_for_status()
        
        # Use regular expressions to find backup* directories
        logger.debug("Parsing page content for backup directories")
        backup_dirs = re.findall(r'href="(backup\d{8})/"', response.text)
        logger.debug(f"Found backup directories: {backup_dirs}")
        
        if not backup_dirs:
            logger.warning("No backup directories found. Using default value.")
            print_warning("No backup directories found. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        # Sort and take the latest (newest) backup
        latest_backup = sorted(backup_dirs)[-1]
        logger.debug(f"Latest backup directory: {latest_backup}")
        print_success(f"Found latest backup: {latest_backup}")
        
        # Form full download URL
        download_url = f"{BASE_URL}{latest_backup}/{ARCHIVE_NAME}"
        logger.debug(f"Full download URL: {download_url}")
        
        # Check file availability
        logger.debug("Checking file availability")
        test_response = requests.head(download_url)
        if test_response.status_code != 200:
            logger.warning(f"File {download_url} is not available. Using default value.")
            print_warning(f"File {download_url} is not available. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        logger.debug(f"File is available, status code: {test_response.status_code}")
        return download_url
    
    except Exception as e:
        logger.error(f"Error finding latest backup: {str(e)}")
        logger.error(traceback.format_exc())
        print_warning(f"Error finding latest backup: {str(e)}. Using default value.")
        return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"

def download_and_extract_db():
    """Download and extract database archive."""
    print_step("Downloading database archive...")
    logger.debug("Starting database archive download and extraction")
    
    try:
        # Get actual download URL
        download_url = find_latest_backup_url()
        logger.debug(f"Download URL determined: {download_url}")
        print(f"Download URL: {download_url}")
        
        # Create output directory if it doesn't exist
        logger.debug(f"Creating output directory: {OUTPUT_DIR}")
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            logger.debug("Output directory created")
        else:
            logger.debug("Output directory already exists")
        
        # Archive file name
        archive_name = os.path.basename(download_url)
        archive_path = f"/tmp/{archive_name}"
        logger.debug(f"Archive path: {archive_path}")
        
        # Download archive with progress indicator
        try:
            logger.debug(f"Starting download from {download_url}")
            print(f"Downloading {download_url}...")
            
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            # Get file size if server provides it
            total_size = int(response.headers.get('content-length', 0))
            logger.debug(f"Total file size: {total_size} bytes")
            
            block_size = 8192
            downloaded = 0
            
            start_time = time.time()
            
            with open(archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Show progress if total size is known
                        if total_size > 0:
                            elapsed_time = time.time() - start_time
                            percent = downloaded / total_size * 100
                            speed = downloaded / (1024 * 1024 * elapsed_time) if elapsed_time > 0 else 0
                            
                            # Log every 5% progress
                            if int(percent) % 5 == 0:
                                logger.debug(f"Download progress: {percent:.1f}% ({downloaded}/{total_size} bytes, {speed:.2f} MB/s)")
                            
                            done = int(50 * downloaded / total_size)
                            progress_bar = f"[{'=' * done}{' ' * (50-done)}]"
                            progress_text = f"{progress_bar} {downloaded}/{total_size} bytes ({percent:.1f}%, {speed:.2f} MB/s)"
                            sys.stdout.write(f"\r{progress_text}")
                            sys.stdout.flush()
            
            if total_size > 0:
                sys.stdout.write('\n')
            
            download_time = time.time() - start_time
            logger.debug(f"Download completed in {download_time:.2f} seconds")
            print_success(f"Archive successfully downloaded in {download_time:.2f} seconds")
        
        except Exception as e:
            logger.error(f"Error downloading archive: {str(e)}")
            logger.error(traceback.format_exc())
            print_error(f"Error downloading archive: {str(e)}")
            sys.exit(1)
        
        # Extract archive
        print_step("Extracting database archive...")
        logger.debug(f"Extracting archive: {archive_path} to {OUTPUT_DIR}")
        
        try:
            with tarfile.open(archive_path) as tar:
                # Check for safe paths during extraction
                logger.debug("Checking for safe paths in archive")
                for member in tar.getmembers():
                    if member.name.startswith(('/')) or '..' in member.name:
                        logger.error(f"Unsafe path in archive: {member.name}")
                        print_error(f"Unsafe path in archive: {member.name}")
                        sys.exit(1)
                
                # Count total number of files for progress indicator
                total_files = len(tar.getmembers())
                logger.debug(f"Total files in archive: {total_files}")
                print(f"Extracting {total_files} files...")
                
                # Extract files with progress indicator
                start_time = time.time()
                for i, member in enumerate(tar.getmembers(), 1):
                    tar.extract(member, path=OUTPUT_DIR)
                    
                    # Log every 5% progress
                    percent = i / total_files * 100
                    if int(percent) % 5 == 0:
                        logger.debug(f"Extraction progress: {percent:.1f}% ({i}/{total_files} files)")
                    
                    # Update progress every 100 files or on last file
                    if i % 100 == 0 or i == total_files:
                        progress = int(i / total_files * 100)
                        sys.stdout.write(f"\rExtraction: {progress}% ({i}/{total_files} files)")
                        sys.stdout.flush()
                
                sys.stdout.write('\n')
                
                extraction_time = time.time() - start_time
                logger.debug(f"Extraction completed in {extraction_time:.2f} seconds")
                print_success(f"Archive successfully extracted in {extraction_time:.2f} seconds")
        
        except Exception as e:
            logger.error(f"Error extracting archive: {str(e)}")
            logger.error(traceback.format_exc())
            print_error(f"Error extracting archive: {str(e)}")
            sys.exit(1)
        
        # Remove archive
        logger.debug(f"Removing downloaded archive: {archive_path}")
        os.remove(archive_path)
        logger.debug("Archive file removed")
    
    except Exception as e:
        logger.error(f"Error in download_and_extract_db function: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error downloading and extracting database: {str(e)}")
        sys.exit(1)

def clone_and_build_java_tron():
    """Clone and build java-tron."""
    print_step("Cloning and building java-tron...")
    logger.debug("Starting java-tron cloning and building")
    
    try:
        # Check if directory exists
        logger.debug(f"Checking if directory exists: {TRON_DIR}")
        if os.path.exists(TRON_DIR):
            logger.debug(f"Directory {TRON_DIR} already exists")
            print_warning(f"Directory {TRON_DIR} already exists. Skipping cloning.")
        else:
            # Create directory if it doesn't exist
            logger.debug(f"Creating directory: {TRON_DIR}")
            os.makedirs(TRON_DIR, exist_ok=True)
            
            # Clone repository
            logger.debug("Cloning java-tron repository")
            clone_cmd = f"git clone https://github.com/tronprotocol/java-tron.git {TRON_DIR}"
            print(f"Executing command: {clone_cmd}")
            run_command(clone_cmd)
            logger.debug("Repository cloning completed")
        
        # Change to directory and checkout master branch
        logger.debug(f"Changing directory to {TRON_DIR}")
        os.chdir(TRON_DIR)
        
        # Run git fetch and checkout
        logger.debug("Fetching latest changes")
        run_command("git fetch")
        
        logger.debug("Checking out master branch")
        checkout_result = run_command("git checkout -t origin/master", check=False)
        logger.debug(f"Checkout result: {checkout_result}")
        
        # Fix build.gradle file to properly add javax.annotation dependency
        gradle_build_file = f"{TRON_DIR}/build.gradle"
        logger.debug(f"Examining build.gradle file: {gradle_build_file}")
        
        if os.path.exists(gradle_build_file):
            logger.debug("build.gradle file exists, checking content")
            with open(gradle_build_file, "r") as f:
                content = f.read()
            
            # Look for dependencies block
            logger.debug("Looking for dependencies block")
            
            # Create a backup of the original file
            with open(f"{gradle_build_file}.bak", "w") as f:
                f.write(content)
            logger.debug("Created backup of build.gradle")
            
            # Find all dependencies blocks - this is more robust
            allprojects_dependencies = re.findall(r'allprojects\s*{[^}]*dependencies\s*{([^}]*)}', content, re.DOTALL)
            logger.debug(f"Found {len(allprojects_dependencies)} allprojects dependencies blocks")
            
            # Check for a way to add the dependency safely
            if allprojects_dependencies:
                # Replace the first occurrence of dependencies within allprojects
                new_content = content
                for block in allprojects_dependencies:
                    if "javax.annotation:javax.annotation-api" not in block:
                        replacement = block + "\n    compile 'javax.annotation:javax.annotation-api:1.3.2'\n"
                        new_content = new_content.replace(block, replacement, 1)
                        logger.debug("Added dependency to allprojects dependencies block")
                        break
                
                with open(gradle_build_file, "w") as f:
                    f.write(new_content)
                logger.debug("Updated build.gradle with annotation dependency")
            else:
                # If we can't find an appropriate block, try another approach
                logger.debug("Could not find appropriate dependencies block, trying direct addition")
                
                # Try to add it directly to the end of the file
                with open(gradle_build_file, "a") as f:
                    f.write("\n\nallprojects {\n    dependencies {\n        compile 'javax.annotation:javax.annotation-api:1.3.2'\n    }\n}\n")
                logger.debug("Appended dependency to build.gradle")
        else:
            logger.warning(f"build.gradle file not found at {gradle_build_file}")
            print_warning("build.gradle file not found. Build may fail.")
        
        # Check gradlew permissions
        logger.debug("Checking gradlew permissions")
        gradlew_path = f"{TRON_DIR}/gradlew"
        if os.path.exists(gradlew_path):
            os.chmod(gradlew_path, os.stat(gradlew_path).st_mode | stat.S_IEXEC)
            logger.debug("Set executable permission for gradlew")
        
        # Build project with detailed output
        print_step("Building java-tron (this may take some time)...")
        logger.debug("Starting java-tron build")
        
        # Create gradlew environment with JAVA_HOME explicitly set
        env = os.environ.copy()
        env["JAVA_HOME"] = "/usr/lib/jvm/java-8-openjdk-amd64"
        logger.debug(f"Set environment JAVA_HOME={env['JAVA_HOME']}")

        print("Build started, please wait (may take 10-20 minutes)...")
        
        # Run build with environment variables set
        build_cmd = f"JAVA_HOME={env['JAVA_HOME']} ./gradlew clean build -x test --info --stacktrace"
        logger.debug(f"Running build command: {build_cmd}")
        
        return_code, live_log_file = run_command_with_live_output(build_cmd, cwd=TRON_DIR)
        
        # Check build success
        if return_code != 0 or not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
            logger.error(f"java-tron build failed with return code {return_code}")
            print_error(f"java-tron build failed (error code: {return_code}).")
            print_error(f"Check build logs: {live_log_file}")
            
            # Special handling for failing build - try fallback approach
            print_warning("Trying fallback approach...")
            logger.warning("Trying fallback approach for build")
            
            # Try an alternative way to add the missing annotation
            logger.debug("Applying fallback solution for javax.annotation dependency")
            
            # Create a local lib directory
            lib_dir = f"{TRON_DIR}/lib"
            os.makedirs(lib_dir, exist_ok=True)
            
            # Download the javax.annotation-api jar directly
            annotation_jar = f"{lib_dir}/javax.annotation-api-1.3.2.jar"
            download_cmd = f"wget -O {annotation_jar} https://repo1.maven.org/maven2/javax/annotation/javax.annotation-api/1.3.2/javax.annotation-api-1.3.2.jar"
            run_command(download_cmd, shell=True)
            
            # Update build.gradle to include the local jar
            with open(gradle_build_file, "a") as f:
                f.write(f"\n\nallprojects {{\n    dependencies {{\n        compile files('{lib_dir}/javax.annotation-api-1.3.2.jar')\n    }}\n}}\n")
            
            # Try build again
            print_step("Retrying build with fallback approach...")
            return_code, live_log_file = run_command_with_live_output(build_cmd, cwd=TRON_DIR)
            
            if return_code != 0 or not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
                logger.error("Fallback build also failed")
                print_error("Fallback build also failed. Installation cannot continue.")
                sys.exit(1)
        
        # Check for FullNode.jar file
        if os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
            jar_size = os.path.getsize(f"{TRON_DIR}/build/libs/FullNode.jar") // (1024 * 1024)  # MB
            logger.debug(f"FullNode.jar found, size: {jar_size} MB")
            print_success(f"java-tron built successfully, FullNode.jar size: {jar_size} MB")
        else:
            logger.error("FullNode.jar not found after build")
            print_error("FullNode.jar not found after build.")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error in clone_and_build_java_tron function: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error cloning and building java-tron: {str(e)}")
        sys.exit(1)

def create_config_files():
    """Create configuration files using existing config."""
    print_step("Setting up configuration files...")
    logger.debug("Starting configuration files setup")
    
    try:
        # Copy existing config file if it exists in the script directory
        src_config = f"{SCRIPT_DIR}/last-conf.conf"
        if os.path.exists(src_config):
            logger.debug(f"Found existing config file at {src_config}, copying to {CONFIG_FILE}")
            shutil.copy2(src_config, CONFIG_FILE)
            print_success("Copied existing configuration file")
        else:
            logger.warning(f"Config file not found at {src_config}, this may cause issues")
            print_warning(f"Configuration file not found at {src_config}")
            print_warning("Node may not start properly. Please ensure 'last-conf.conf' exists in the same directory as this script.")
        
        # Startup script content
        logger.debug(f"Creating startup script: {START_SCRIPT}")
        start_script_content = """#!/bin/bash
java -Xmx24g -XX:+UseConcMarkSweepGC -jar /home/java-tron/build/libs/FullNode.jar -c /home/java-tron/last-conf.conf -d /home/java-tron/output-directory/
"""
        
        # Write startup script
        with open(START_SCRIPT, "w") as f:
            f.write(start_script_content)
        logger.debug("Startup script created")
        
        # Set execute permissions
        logger.debug("Setting execute permissions for startup script")
        os.chmod(START_SCRIPT, os.stat(START_SCRIPT).st_mode | stat.S_IEXEC)
        
        # Create systemd service content
        logger.debug(f"Creating systemd service file: {SYSTEMD_SERVICE}")
        systemd_service_content = """[Unit]
Description=TRON Full Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/java-tron
ExecStart=/bin/bash /home/java-tron/last-node-start.sh
Restart=on-failure
RestartSec=10
LimitNOFILE=500000

[Install]
WantedBy=multi-user.target
"""
        
        # Write systemd service
        with open(SYSTEMD_SERVICE, "w") as f:
            f.write(systemd_service_content)
        logger.debug("Systemd service file created")
        
        # Create README.md
        logger.debug("Creating README.md file")
        readme_content = """# TRON Lite Full Node

## Installation

Node was automatically installed via installation script.

## Basic Commands

### Check Node Status
```bash
systemctl status tron-node
