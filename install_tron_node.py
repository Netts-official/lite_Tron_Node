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
import datetime
from datetime import datetime
import traceback

# Setting up the logging directory to script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = SCRIPT_DIR
LOG_FILE = f"{LOG_DIR}/installation.log"

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
DEBUG_LOG = f"{TRON_DIR}/debug.log"

# Base URL for downloading archive (actual link will be determined automatically)
BASE_URL = "http://34.86.86.229/"

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
    command_log_file = f"{LOG_DIR}/command_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
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
    command_log_file = f"{LOG_DIR}/command_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
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

def check_system_resources():
    """Check system resources."""
    logger.debug("Checking system resources")
    
    # Check available memory
    try:
        with open('/proc/meminfo', 'r') as f:
            mem_info = f.read()
        
        # Extract memory information
        total_mem = int(re.search(r'MemTotal:\s+(\d+)', mem_info).group(1)) // 1024  # MB
        free_mem = int(re.search(r'MemFree:\s+(\d+)', mem_info).group(1)) // 1024  # MB
        available_mem = int(re.search(r'MemAvailable:\s+(\d+)', mem_info).group(1)) // 1024  # MB
        
        logger.debug(f"Total memory: {total_mem} MB")
        logger.debug(f"Free memory: {free_mem} MB")
        logger.debug(f"Available memory: {available_mem} MB")
        
        if total_mem < 15000:  # Less than 15 GB
            logger.warning(f"System has only {total_mem} MB of total memory. Minimum recommended is 16 GB.")
            print_warning(f"System has only {total_mem} MB of total memory. Minimum recommended is 16 GB.")
    
    except Exception as e:
        logger.error(f"Error checking memory: {str(e)}")
        print_warning("Could not check available memory.")
    
    # Check available disk space
    try:
        disk_info = os.statvfs('/home')
        total_space = disk_info.f_frsize * disk_info.f_blocks // (1024 * 1024 * 1024)  # GB
        free_space = disk_info.f_frsize * disk_info.f_bfree // (1024 * 1024 * 1024)  # GB
        
        logger.debug(f"Total disk space: {total_space} GB")
        logger.debug(f"Free disk space: {free_space} GB")
        
        if free_space < 500:  # Less than 500 GB
            logger.warning(f"System has only {free_space} GB of free disk space. Minimum recommended is 500 GB.")
            print_warning(f"System has only {free_space} GB of free disk space. Minimum recommended is 500 GB.")
    
    except Exception as e:
        logger.error(f"Error checking disk space: {str(e)}")
        print_warning("Could not check available disk space.")
    
    # Check number of processors
    try:
        cpu_count = os.cpu_count()
        logger.debug(f"CPU count: {cpu_count}")
        
        if cpu_count < 4:
            logger.warning(f"System has only {cpu_count} CPU cores. Minimum recommended is 4 cores.")
            print_warning(f"System has only {cpu_count} CPU cores. Minimum recommended is 4 cores.")
    
    except Exception as e:
        logger.error(f"Error checking CPU count: {str(e)}")
        print_warning("Could not check number of processors.")
    
    logger.debug("System resource check completed")

def install_dependencies():
    """Install required dependencies."""
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
    
    try:
        # Check installed Java versions
        logger.debug("Checking installed Java versions")
        java_versions_output = run_command("update-alternatives --list java", check=False)
        logger.debug(f"Installed Java versions: {java_versions_output}")
        
        if java_versions_output and "java-8" in java_versions_output:
            logger.debug("Java 8 is installed, configuring as default")
            
            # Get Java configuration options
            logger.debug("Getting Java configuration options")
            java_config_cmd = "update-alternatives --config java"
            print_debug(f"Getting Java configuration options: {java_config_cmd}")
            
            process = subprocess.Popen(
                java_config_cmd,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            logger.debug(f"Java configuration options: {stdout}")
            if stderr:
                logger.warning(f"Java configuration stderr: {stderr}")
            
            # Find Java 8 option
            lines = stdout.strip().split('\n')
            java8_option = None
            
            for line in lines:
                logger.debug(f"Processing line: {line}")
                if "java-8" in line:
                    parts = line.split()
                    logger.debug(f"Found Java 8 line, parts: {parts}")
                    if parts and len(parts) > 0:
                        java8_option = parts[0].strip()
                        logger.debug(f"Java 8 option: {java8_option}")
            
            if java8_option:
                # Set Java 8 via echo
                logger.debug(f"Setting Java 8 as default using option {java8_option}")
                run_command(f"echo {java8_option} | update-alternatives --config java", shell=True)
                
                # Configure javac
                logger.debug("Configuring javac")
                javac_config_cmd = "update-alternatives --config javac"
                print_debug(f"Getting javac configuration options: {javac_config_cmd}")
                
                process = subprocess.Popen(
                    javac_config_cmd,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate()
                logger.debug(f"Javac configuration options: {stdout}")
                if stderr:
                    logger.warning(f"Javac configuration stderr: {stderr}")
                
                # Find Javac 8 option
                lines = stdout.strip().split('\n')
                javac8_option = None
                
                for line in lines:
                    logger.debug(f"Processing javac line: {line}")
                    if "java-8" in line:
                        parts = line.split()
                        logger.debug(f"Found Javac 8 line, parts: {parts}")
                        if parts and len(parts) > 0:
                            javac8_option = parts[0].strip()
                            logger.debug(f"Javac 8 option: {javac8_option}")
                
                if javac8_option:
                    logger.debug(f"Setting Javac 8 as default using option {javac8_option}")
                    run_command(f"echo {javac8_option} | update-alternatives --config javac", shell=True)
        
        # Check Java version
        logger.debug("Checking current Java version")
        java_version = run_command("java -version 2>&1", check=False, shell=True)
        logger.debug(f"Current Java version: {java_version}")
        
        if java_version and "1.8" not in java_version:
            logger.warning("Java 8 is not set as the main version. Setting manually...")
            print_warning("Java 8 is not set as the main version. Setting manually...")
            
            # Set Java 8 as default via update-alternatives
            logger.debug("Setting Java 8 manually")
            run_command("update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java")
            run_command("update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac")
        
        # Verify again
        logger.debug("Verifying Java 8 configuration")
        java_version = run_command("java -version 2>&1 | grep version", shell=True)
        logger.debug(f"Java version after configuration: {java_version}")
        
        if "1.8" in java_version:
            print_success("Java 8 configured as main version")
            logger.debug("Java 8 configured as main version")
        else:
            logger.error("Failed to configure Java 8")
            print_error("Failed to configure Java 8")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error configuring Java 8: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error configuring Java 8: {str(e)}")
        sys.exit(1)

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
        
        # Add dependency for javax.annotation.Generated
        gradle_build_file = f"{TRON_DIR}/build.gradle"
        logger.debug(f"Checking build.gradle file: {gradle_build_file}")
        
        if os.path.exists(gradle_build_file):
            logger.debug("build.gradle file exists, checking for dependency")
            with open(gradle_build_file, "r") as file:
                content = file.read()
            
            # Check if dependency already exists
            if "javax.annotation:javax.annotation-api" not in content:
                logger.debug("Adding javax.annotation dependency to build.gradle")
                dependency_line = "dependencies {\n    implementation 'javax.annotation:javax.annotation-api:1.3.2'"
                content = content.replace("dependencies {", dependency_line)
                
                with open(gradle_build_file, "w") as file:
                    file.write(content)
                logger.debug("Dependency added to build.gradle")
            else:
                logger.debug("javax.annotation dependency already exists in build.gradle")
        else:
            logger.warning(f"build.gradle file not found at {gradle_build_file}")
        
        # Check gradlew permissions
        logger.debug("Checking gradlew permissions")
        gradlew_path = f"{TRON_DIR}/gradlew"
        if os.path.exists(gradlew_path):
            os.chmod(gradlew_path, os.stat(gradlew_path).st_mode | stat.S_IEXEC)
            logger.debug("Set executable permission for gradlew")
        
        # Build project with detailed output
        print_step("Building java-tron (this may take some time)...")
        logger.debug("Starting java-tron build")
        
        # Create file for build logs
        build_log_file = f"{LOG_DIR}/build.log"
        logger.debug(f"Build log will be saved to: {build_log_file}")
        
        print("Build started, please wait (may take 10-20 minutes)...")
        print("Detailed build output will be saved to log file.")
        
        # Run build with real-time output
        build_cmd = "./gradlew clean build -x test --info --stacktrace"
        logger.debug(f"Running build command: {build_cmd}")
        
        return_code, live_log_file = run_command_with_live_output(build_cmd, cwd=TRON_DIR)
        
        # Check build success
        if return_code != 0 or not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
            logger.error(f"java-tron build failed with return code {return_code}")
            print_error(f"java-tron build failed (error code: {return_code}).")
            print_error(f"Check build logs: {live_log_file}")
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
    """Create configuration files."""
    print_step("Creating configuration files...")
    logger.debug("Starting configuration files creation")
    
    try:
        # Configuration file content
        logger.debug(f"Creating configuration file: {CONFIG_FILE}")
        config_content = """storage {
  # Directory for storing persistent data
  db.engine = "LEVELDB",
  db.sync = true,
  db.directory = "database",
  index.directory = "index",
  transHistory.switch = "on",
  # You can custom these 14 databases' configs:

  # account, account-index, asset-issue, block, block-index,
  # block_KDB, peers, properties, recent-block, trans,
  # utxo, votes, witness, witness_schedule.

  # Otherwise, db configs will remain default and data will be stored in
  # the path of "output-directory" or which is set by "-d" ("--output-directory").
  # setting can impove leveldb performance .... start
  # node: if this will increase process fds,you may be check your ulimit if 'too many open files' error occurs
  # see https://github.com/tronprotocol/tips/blob/master/tip-343.md for detail
  # if you find block sync has lower performance,you can try  this  settings
  #default = {
  #  maxOpenFiles = 100
  #}
  #defaultM = {
  #  maxOpenFiles = 500
  #}
  defaultL = {
    maxOpenFiles = 3000
  }
  # setting can impove leveldb performance .... end
  # Attention: name is a required field that must be set !!!
  properties = [
    //    {
    //      name = "account",
    //      path = "storage_directory_test",
    //      createIfMissing = true,
    //      paranoidChecks = true,
    //      verifyChecksums = true,
    //      compressionType = 1,        // compressed with snappy
    //      blockSize = 4096,           // 4  KB =         4 * 1024 B
    //      writeBufferSize = 10485760, // 10 MB = 10 * 1024 * 1024 B
    //      cacheSize = 10485760,       // 10 MB = 10 * 1024 * 1024 B
    //      maxOpenFiles = 100
    //    },
    //    {
    //      name = "account-index",
    //      path = "storage_directory_test",
    //      createIfMissing = true,
    //      paranoidChecks = true,
    //      verifyChecksums = true,
    //      compressionType = 1,        // compressed with snappy
    //      blockSize = 4096,           // 4  KB =         4 * 1024 B
    //      writeBufferSize = 10485760, // 10 MB = 10 * 1024 * 1024 B
    //      cacheSize = 10485760,       // 10 MB = 10 * 1024 * 1024 B
    //      maxOpenFiles = 100
    //    },
  ]

  needToUpdateAsset = true

  //dbsettings is needed when using rocksdb as the storage implement (db.engine="ROCKSDB").
  //we'd strongly recommend that do not modify it unless you know every item's meaning clearly.
  dbSettings = {
    levelNumber = 7
    //compactThreads = 32
    blocksize = 64  // n * KB
    maxBytesForLevelBase = 256  // n * MB
    maxBytesForLevelMultiplier = 10
    level0FileNumCompactionTrigger = 4
    targetFileSizeBase = 256  // n * MB
    targetFileSizeMultiplier = 1
  }

  //backup settings when using rocks db as the storage implement (db.engine="ROCKSDB").
  //if you want to use the backup plugin, please confirm set the db.engine="ROCKSDB" above.
  backup = {
    enable = false  // indicate whether enable the backup plugin
    propPath = "prop.properties" // record which bak directory is valid
    bak1path = "bak1/database" // you must set two backup directories to prevent application halt unexpected(e.g. kill -9).
    bak2path = "bak2/database"
    frequency = 10000   // indicate backup db once every 10000 blocks processed.
  }

  balance.history.lookup = true

  # checkpoint.version = 2
  # checkpoint.sync = true

  # the estimated number of block transactions (default 1000, min 100, max 10000).
  # so the total number of cached transactions is 65536 * txCache.estimatedTransactions
  # txCache.estimatedTransactions = 1000

  # data root setting, for check data, currently, only reward-vi is used.

  # merkleRoot = {
  # reward-vi = 9debcb9924055500aaae98cdee10501c5c39d4daa75800a996f4bdda73dbccd8 // main-net, Sha256Hash, hexString
  # }
}

node.discovery = {
  enable = true
  persist = true
}

# custom stop condition
#node.shutdown = {
#  BlockTime  = "54 59 08 * * ?" # if block header time in persistent db matched.
#  BlockHeight = 33350800 # if block header height in persistent db matched.
#  BlockCount = 12 # block sync count after node start.
#}

node.backup {
  # udp listen port, each member should have the same configuration
  port = 10001

  # my priority, each member should use different priority
  priority = 8

  # time interval to send keepAlive message, each member should have the same configuration
  keepAliveInterval = 3000

  # peer's ip list, can't contain mine
  members = [
    # "ip",
    # "ip"
  ]
}

crypto {
  engine = "eckey"
}
 # prometheus metrics start
 node.metrics = {
  prometheus{
    enable=true
    port="9527"
  }
}

# prometheus metrics end

node {
  # trust node for solidity node
  # trustNode = "ip:port"
  # #trustNode = "127.0.0.1:50051"

  # expose extension api to public or not
  walletExtensionApi = true

  listen.port = 18888

  connection.timeout = 2

  fetchBlock.timeout = 200

  tcpNettyWorkThreadNum = 16

  udpNettyWorkThreadNum = 8

  # Number of validate sign thread, default availableProcessors / 2
  # validateSignThreadNum = 16

  maxConnections = 100

  minConnections = 8

  minActiveConnections = 10

  maxConnectionsWithSameIp = 2

  maxHttpConnectNumber = 5000

  minParticipationRate = 0

  isOpenFullTcpDisconnect = false

  p2p {
    version = 11111 # 11111: mainnet; 20180622: testnet
    max_peers = 50
  }

  active = [
    # Active establish connection in any case
    # Sample entries:
    # "ip:port",
    # "ip:port"
  ]

  passive = [
    # Passive accept connection in any case
    # Sample entries:
    # "ip:port",
    # "ip:port"
  ]

  fastForward = [
    "100.26.245.209:18888",
    "15.188.6.125:18888"
  ]
  http {
    fullNodeEnable = true
    fullNodePort = 8090
    solidityEnable = true
    solidityPort = 8091
    bindAddress = "0.0.0.0"
    maxHttpConnectNumber = 5000
    connection.timeout = 30
  }


  rpc {
    port = 50051
    #solidityPort = 50061
    # Number of gRPC thread, default availableProcessors / 2
    thread = 16

    # The maximum number of concurrent calls permitted for each incoming connection
    # maxConcurrentCallsPerConnection =

    # The HTTP/2 flow control window, default 1MB
    # flowControlWindow =

    # Connection being idle for longer than which will be gracefully terminated
    maxConnectionIdleInMillis = 60000

    # Connection lasting longer than which will be gracefully terminated
    # maxConnectionAgeInMillis =

    # The maximum message size allowed to be received on the server, default 4MB
    maxMessageSize = 33554432

    # The maximum size of header list allowed to be received, default 8192
    # maxHeaderListSize =

    # Transactions can only be broadcast if the number of effective connections is reached.
    minEffectiveConnection = 3
   
    # The switch of the reflection service, effective for all gRPC services
    # reflectionService = true
  }

  # number of solidity thread in the FullNode.
  # If accessing solidity rpc and http interface timeout, could increase the number of threads,
  # The default value is the number of cpu cores of the machine.
  #solidity.threads = 8

  # Limits the maximum percentage (default 75%) of producing block interval
  # to provide sufficient time to perform other operations e.g. broadcast block
  # blockProducedTimeOut = 75

  # Limits the maximum number (default 700) of transaction from network layer
  # netMaxTrxPerSecond = 700

  # Whether to enable the node detection function, default false
  # nodeDetectEnable = false

  # use your ipv6 address for node discovery and tcp connection, default false
  # enableIpv6 = false

  # if your node's highest block num is below than all your pees', try to acquire new connection. default false
  # effectiveCheckEnable = false

  # Dynamic loading configuration function, disabled by default
  # dynamicConfig = {
    # enable = false
    # Configuration file change check interval, default is 600 seconds
    # checkInterval = 600
  # }

  dns {
    # dns urls to get nodes, url format tree://{pubkey}@{domain}, default empty
    treeUrls = [
      #"tree://AKMQMNAJJBL73LXWPXDI4I5ZWWIZ4AWO34DWQ636QOBBXNFXH3LQS@main.trondisco.net", //offical dns tree
    ]

    # enable or disable dns publish, default false
    # publish = false

    # dns domain to publish nodes, required if publish is true
    # dnsDomain = "nodes1.example.org"

    # dns private key used to publish, required if publish is true, hex string of length 64
    # dnsPrivate = "b71c71a67e1177ad4e901695e1b4b9ee17ae16c6668d313eac2f96dbcda3f291"

    # known dns urls to publish if publish is true, url format tree://{pubkey}@{domain}, default empty
    # knownUrls = [
    #"tree://APFGGTFOBVE2ZNAB3CSMNNX6RRK3ODIRLP2AA5U4YFAA6MSYZUYTQ@nodes2.example.org",
    # ]

    # staticNodes = [
    # static nodes to published on dns
    # Sample entries:
    # "ip:port",
    # "ip:port"
    # ]

    # merge several nodes into a leaf of tree, should be 1~5
    # maxMergeSize = 5

    # only nodes change percent is bigger then the threshold, we update data on dns
    # changeThreshold = 0.1

    # dns server to publish, required if publish is true, only aws or aliyun is support
    # serverType = "aws"

    # access key id of aws or aliyun api, required if publish is true, string
    # accessKeyId = "your-key-id"

    # access key secret of aws or aliyun api, required if publish is true, string
    # accessKeySecret = "your-key-secret"

    # if publish is true and serverType is aliyun, it's endpoint of aws dns server, string
    # aliyunDnsEndpoint = "alidns.aliyuncs.com"

    # if publish is true and serverType is aws, it's region of aws api, such as "eu-south-1", string
    # awsRegion = "us-east-1"

    # if publish is true and server-type is aws, it's host zone id of aws's domain, string
    # awsHostZoneId = "your-host-zone-id"
  }

  # open the history query APIs(http&GRPC) when node is a lite fullNode,
  # like {getBlockByNum, getBlockByID, getTransactionByID...}.
  # default: false.
  # note: above APIs may return null even if blocks and transactions actually are on the blockchain
  # when opening on a lite fullnode. only open it if the consequences being clearly known
  openHistoryQueryWhenLiteFN = true

  jsonrpc {
    # Note: If you turn on jsonrpc and run it for a while and then turn it off, you will not
    # be able to get the data from eth_getLogs for that period of time.

    httpFullNodeEnable = true
    httpFullNodePort = 8545
    httpSolidityEnable = true
    httpSolidityPort = 8555
    httpPBFTEnable = true
    httpPBFTPort = 8565
  }

  # Disabled api list, it will work for http, rpc and pbft, both fullnode and soliditynode,
  # but not jsonrpc.
  # Sample: The setting is case insensitive, GetNowBlock2 is equal to getnowblock2
  #
  # disabledApi = [
  #   "getaccount",
  #   "getnowblock2"
  # ]
}

## rate limiter config
rate.limiter = {
  # Every api could be set a specific rate limit strategy. Three strategy are supported:GlobalPreemptibleAdapter、IPQPSRateLimiterAdapte、QpsRateLimiterAdapter
  # GlobalPreemptibleAdapter: permit is the number of preemptible resource, every client must apply one resourse
  #       before do the request and release the resource after got the reponse automaticlly. permit should be a Integer.
  # QpsRateLimiterAdapter: qps is the average request count in one second supported by the server, it could be a Double or a Integer.
  # IPQPSRateLimiterAdapter: similar to the QpsRateLimiterAdapter, qps could be a Double or a Integer.
  # If do not set, the "default strategy" is set.The "default startegy" is based on QpsRateLimiterAdapter, the qps is set as 10000.
  #
  # Sample entries:
  #
  http = [
    #  {
    #    component = "GetNowBlockServlet",
    #    strategy = "GlobalPreemptibleAdapter",
    #    paramString = "permit=1"
    #  },

    #  {
    #    component = "GetAccountServlet",
    #    strategy = "IPQPSRateLimiterAdapter",
    #    paramString = "qps=1"
    #  },

    #  {
    #    component = "ListWitnessesServlet",
    #    strategy = "QpsRateLimiterAdapter",
    #    paramString = "qps=1"
    #  }
  ],

  rpc = [
    #  {
    #    component = "protocol.Wallet/GetBlockByLatestNum2",
    #    strategy = "GlobalPreemptibleAdapter",
    #    paramString = "permit=1"
    #  },

    #  {
    #    component = "protocol.Wallet/GetAccount",
    #    strategy = "IPQPSRateLimiterAdapter",
    #    paramString = "qps=1"
    #  },

    #  {
    #    component = "protocol.Wallet/ListWitnesses",
    #    strategy = "QpsRateLimiterAdapter",
    #    paramString = "qps=1"
    #  },
  ]

  # global qps, default 50000
  global.qps = 100000
  # IP-based global qps, default 10000
  global.ip.qps = 20000
}



seed.node = {
  # List of the seed nodes
  # Seed nodes are stable full nodes
  # example:
  # ip.list = [
  #   "ip:port",
  #   "ip:port"
  # ]
  ip.list = [
    "3.225.171.164:18888",
    "52.53.189.99:18888",
    "18.196.99.16:18888",
    "34.253.187.192:18888",
    "18.133.82.227:18888",
    "35.180.51.163:18888",
    "54.252.224.209:18888",
    "18.231.27.82:18888",
    "52.15.93.92:18888",
    "34.220.77.106:18888",
    "15.207.144.3:18888",
    "13.124.62.58:18888",
    "54.151.226.240:18888",
    "35.174.93.198:18888",
    "18.210.241.149:18888",
    "54.177.115.127:18888",
    "54.254.131.82:18888",
    "18.167.171.167:18888",
    "54.167.11.177:18888",
    "35.74.7.196:18888",
    "52.196.244.176:18888",
    "54.248.129.19:18888",
    "43.198.142.160:18888",
    "3.0.214.7:18888",
    "54.153.59.116:18888",
    "54.153.94.160:18888",
    "54.82.161.39:18888",
    "54.179.207.68:18888",
    "18.142.82.44:18888",
    "18.163.230.203:18888",
    # "[2a05:d014:1f2f:2600:1b15:921:d60b:4c60]:18888", // use this if support ipv6
    # "[2600:1f18:7260:f400:8947:ebf3:78a0:282b]:18888", // use this if support ipv6
  ]
}

genesis.block = {
  # Reserve balance
  assets = [
    {
      accountName = "Zion"
      accountType = "AssetIssue"
      address = "TLLM21wteSPs4hKjbxgmH1L6poyMjeTbHm"
      balance = "99000000000000000"
    },
    {
      accountName = "Sun"
      accountType = "AssetIssue"
      address = "TXmVpin5vq5gdZsciyyjdZgKRUju4st1wM"
      balance = "0"
    },
    {
      accountName = "Blackhole"
      accountType = "AssetIssue"
      address = "TLsV52sRDL79HXGGm9yzwKibb6BeruhUzy"
      balance = "-9223372036854775808"
    }
  ]

  witnesses = [
    {
      address: THKJYuUmMKKARNf7s2VT51g5uPY6KEqnat,
      url = "http://GR1.com",
      voteCount = 100000026
    },
    {
      address: TVDmPWGYxgi5DNeW8hXrzrhY8Y6zgxPNg4,
      url = "http://GR2.com",
      voteCount = 100000025
    },
    {
      address: TWKZN1JJPFydd5rMgMCV5aZTSiwmoksSZv,
      url = "http://GR3.com",
      voteCount = 100000024
    },
    {
      address: TDarXEG2rAD57oa7JTK785Yb2Et32UzY32,
      url = "http://GR4.com",
      voteCount = 100000023
    },
    {
      address: TAmFfS4Tmm8yKeoqZN8x51ASwdQBdnVizt,
      url = "http://GR5.com",
      voteCount = 100000022
    },
    {
      address: TK6V5Pw2UWQWpySnZyCDZaAvu1y48oRgXN,
      url = "http://GR6.com",
      voteCount = 100000021
    },
    {
      address: TGqFJPFiEqdZx52ZR4QcKHz4Zr3QXA24VL,
      url = "http://GR7.com",
      voteCount = 100000020
    },
    {
      address: TC1ZCj9Ne3j5v3TLx5ZCDLD55MU9g3XqQW,
      url = "http://GR8.com",
      voteCount = 100000019
    },
    {
      address: TWm3id3mrQ42guf7c4oVpYExyTYnEGy3JL,
      url = "http://GR9.com",
      voteCount = 100000018
    },
    {
      address: TCvwc3FV3ssq2rD82rMmjhT4PVXYTsFcKV,
      url = "http://GR10.com",
      voteCount = 100000017
    },
    {
      address: TFuC2Qge4GxA2U9abKxk1pw3YZvGM5XRir,
      url = "http://GR11.com",
      voteCount = 100000016
    },
    {
      address: TNGoca1VHC6Y5Jd2B1VFpFEhizVk92Rz85,
      url = "http://GR12.com",
      voteCount = 100000015
    },
    {
      address: TLCjmH6SqGK8twZ9XrBDWpBbfyvEXihhNS,
      url = "http://GR13.com",
      voteCount = 100000014
    },
    {
      address: TEEzguTtCihbRPfjf1CvW8Euxz1kKuvtR9,
      url = "http://GR14.com",
      voteCount = 100000013
    },
    {
      address: TZHvwiw9cehbMxrtTbmAexm9oPo4eFFvLS,
      url = "http://GR15.com",
      voteCount = 100000012
    },
    {
      address: TGK6iAKgBmHeQyp5hn3imB71EDnFPkXiPR,
      url = "http://GR16.com",
      voteCount = 100000011
    },
    {
      address: TLaqfGrxZ3dykAFps7M2B4gETTX1yixPgN,
      url = "http://GR17.com",
      voteCount = 100000010
    },
    {
      address: TX3ZceVew6yLC5hWTXnjrUFtiFfUDGKGty,
      url = "http://GR18.com",
      voteCount = 100000009
    },
    {
      address: TYednHaV9zXpnPchSywVpnseQxY9Pxw4do,
      url = "http://GR19.com",
      voteCount = 100000008
    },
    {
      address: TCf5cqLffPccEY7hcsabiFnMfdipfyryvr,
      url = "http://GR20.com",
      voteCount = 100000007
    },
    {
      address: TAa14iLEKPAetX49mzaxZmH6saRxcX7dT5,
      url = "http://GR21.com",
      voteCount = 100000006
    },
    {
      address: TBYsHxDmFaRmfCF3jZNmgeJE8sDnTNKHbz,
      url = "http://GR22.com",
      voteCount = 100000005
    },
    {
      address: TEVAq8dmSQyTYK7uP1ZnZpa6MBVR83GsV6,
      url = "http://GR23.com",
      voteCount = 100000004
    },
    {
      address: TRKJzrZxN34YyB8aBqqPDt7g4fv6sieemz,
      url = "http://GR24.com",
      voteCount = 100000003
    },
    {
      address: TRMP6SKeFUt5NtMLzJv8kdpYuHRnEGjGfe,
      url = "http://GR25.com",
      voteCount = 100000002
    },
    {
      address: TDbNE1VajxjpgM5p7FyGNDASt3UVoFbiD3,
      url = "http://GR26.com",
      voteCount = 100000001
    },
    {
      address: TLTDZBcPoJ8tZ6TTEeEqEvwYFk2wgotSfD,
      url = "http://GR27.com",
      voteCount = 100000000
    }
  ]

  timestamp = "0" #2017-8-26 12:00:00

  parentHash = "0xe58f33f9baf9305dc6f82b9f1934ea8f0ade2defb951258d50167028c780351f"
}

// Optional.The default is empty.
// It is used when the witness account has set the witnessPermission.
// When it is not empty, the localWitnessAccountAddress represents the address of the witness account,
// and the localwitness is configured with the private key of the witnessPermissionAddress in the witness account.
// When it is empty,the localwitness is configured with the private key of the witness account.

//localWitnessAccountAddress =

localwitness = [
]

#localwitnesskeystore = [
#  "localwitnesskeystore.json"
#]

block = {
  needSyncCheck = true
  maintenanceTimeInterval = 21600000
  proposalExpireTime = 259200000 // 3 day: 259200000(ms)
}

# Transaction reference block, default is "solid", configure to "head" may incur TaPos error
# trx.reference.block = "solid" // head;solid;

# This property sets the number of milliseconds after the creation of the transaction that is expired, default value is  60000.
# trx.expiration.timeInMilliseconds = 60000

vm = {
  supportConstant = true
  maxEnergyLimitForConstant = 300000000
  minTimeRatio = 0.0
  maxTimeRatio = 5.0
  saveInternalTx = false

  # Indicates whether the node stores featured internal transactions, such as freeze, vote and so on
  # saveFeaturedInternalTx = false

  # In rare cases, transactions that will be within the specified maximum execution time (default 10(ms)) are re-executed and packaged
  # longRunningTime = 10

  # Indicates whether the node support estimate energy API.
  estimateEnergy = true
  # Indicates the max retry time for executing transaction in estimating energy.
  # estimateEnergyMaxRetry = 3
}

committee = {
  allowCreationOfContracts = 0  //mainnet:0 (reset by committee),test:1
  allowAdaptiveEnergy = 0  //mainnet:0 (reset by committee),test:1
}

event.subscribe = {
    native = {
      useNativeQueue = true // if true, use native message queue, else use event plugin.
      bindport = 5555 // bind port
      sendqueuelength = 1000 //max length of send queue
    }

    path = "" // absolute path of plugin
    server = "" // target server address to receive event triggers
    // dbname|username|password, if you want to create indexes for collections when the collections
    // are not exist, you can add version and set it to 2, as dbname|username|password|version
    // if you use version 2 and one collection not exists, it will create index automaticaly;
    // if you use version 2 and one collection exists, it will not create index, you must create index manually;
    dbconfig = ""
    contractParse = true
    topics = [
        {
          triggerName = "block" // block trigger, the value can't be modified
          enable = false
          topic = "block" // plugin topic, the value could be modified
          solidified = false // if set true, just need solidified block, default is false
        },
        {
          triggerName = "transaction"
          enable = true
          topic = "transaction"
          solidified = false
          ethCompatible = false // if set true, add transactionIndex, cumulativeEnergyUsed, preCumulativeLogCount, logList, energyUnitPrice, default is false
        },
        {
          triggerName = "contractevent"
          enable = false
          topic = "contractevent"
        },
        {
          triggerName = "contractlog"
          enable = false
          topic = "contractlog"
          redundancy = false // if set true, contractevent will also be regarded as contractlog
        },
        {
          triggerName = "solidity" // solidity block trigger(just include solidity block number and timestamp), the value can't be modified
          enable = true            // the default value is true
          topic = "solidity"
        },
        {
          triggerName = "solidityevent"
          enable = false
          topic = "solidityevent"
        },
        {
          triggerName = "soliditylog"
          enable = false
          topic = "soliditylog"
          redundancy = false // if set true, solidityevent will also be regarded as soliditylog
        }
    ]

    filter = {
       fromblock = "" // the value could be "", "earliest" or a specified block number as the beginning of the queried range
       toblock = "" // the value could be "", "latest" or a specified block number as end of the queried range
       contractAddress = [
           "" // contract address you want to subscribe, if it's set to "", you will receive contract logs/events with any contract address.
       ]

       contractTopic = [
           "" // contract topic you want to subscribe, if it's set to "", you will receive contract logs/events with any contract topic.
       ]
    }
}"""
        
        # Write configuration file
        with open(CONFIG_FILE, "w") as f:
            f.write(config_content)
        logger.debug("Configuration file created")
        
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
        
        # systemd service content
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
```

### Start Node
```bash
systemctl start tron-node
```

### Stop Node
```bash
systemctl stop tron-node
```

### Restart Node
```bash
systemctl restart tron-node
```

### Enable Autostart
```bash
systemctl enable tron-node
```

### Check Running Processes
```bash
ps aux | grep [F]ullNode
```

### Check Node Information
```bash
curl http://127.0.0.1:8090/wallet/getnodeinfo
```

### Check Current Block
```bash
curl http://127.0.0.1:8090/wallet/getnowblock
```

### Manual Node Start (if needed)
```bash
cd /home/java-tron
chmod +x last-node-start.sh
nohup bash last-node-start.sh &> /dev/null &
```

## Logs

View node logs with:
```bash
journalctl -u tron-node -f
```

## Installation Logs

Installation logs can be found at:
```bash
[SCRIPT_DIR]/installation.log
```

## Debug Information

For detailed debug information, check:
```bash
[SCRIPT_DIR]/command_*.log
```
"""
        
        # Write README.md
        with open(f"{TRON_DIR}/README.md", "w") as f:
            f.write(readme_content)
        logger.debug("README.md file created")
        
        print_success("Configuration files created")
    
    except Exception as e:
        logger.error(f"Error creating configuration files: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error creating configuration files: {str(e)}")
        sys.exit(1)

def setup_systemd():
    """Configure autostart via systemd."""
    print_step("Setting up autostart via systemd...")
    logger.debug("Starting systemd configuration")
    
    try:
        # Reload systemd to detect new service
        logger.debug("Reloading systemd daemon")
        run_command("systemctl daemon-reload")
        
        # Enable autostart
        logger.debug("Enabling tron-node service")
        run_command("systemctl enable tron-node")
        
        # Check status
        logger.debug("Checking service status")
        service_status = run_command("systemctl is-enabled tron-node", check=False)
        logger.debug(f"Service status: {service_status}")
        
        if service_status == "enabled":
            print_success("Autostart configured")
            logger.debug("Autostart configured successfully")
        else:
            print_warning("Failed to configure autostart. Current status: " + service_status)
            logger.warning(f"Failed to configure autostart. Current status: {service_status}")
    
    except Exception as e:
        logger.error(f"Error configuring systemd: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error configuring systemd: {str(e)}")
        sys.exit(1)

def start_node():
    """Start the node."""
    print_step("Starting TRON node...")
    logger.debug("Starting TRON node")
    
    try:
        # Start service
        logger.debug("Starting tron-node service")
        run_command("systemctl start tron-node")
        
        # Check status
        logger.debug("Waiting 5 seconds before checking status")
        time.sleep(5)  # Give time to start
        
        status = run_command("systemctl is-active tron-node", check=False)
        logger.debug(f"Service active status: {status}")
        
        if status == "active":
            print_success("TRON node started successfully!")
            logger.debug("TRON node started successfully")
        else:
            print_warning("TRON node is starting, check status in a few minutes with 'systemctl status tron-node'")
            logger.warning("TRON node is starting, status should be checked later")
            
        # Check log files
        logger.debug("Checking for tron-node service logs")
        service_logs = run_command("journalctl -u tron-node -n 10 --no-pager", check=False)
        logger.debug(f"Recent service logs:\n{service_logs}")
    
    except Exception as e:
        logger.error(f"Error starting node: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error starting node: {str(e)}")
        sys.exit(1)

def check_node_status():
    """Check node status after startup."""
    print_step("Checking TRON node status...")
    logger.debug("Checking TRON node status")
    
    try:
        # Check systemd service status
        logger.debug("Checking systemd service status")
        systemd_status = run_command("systemctl status tron-node --no-pager", check=False)
        logger.debug(f"Systemd status output:\n{systemd_status}")
        
        # Check running processes
        logger.debug("Checking running processes")
        processes = run_command("ps aux | grep [F]ullNode", check=False)
        logger.debug(f"Running processes:\n{processes}")
        
        # Check open ports
        logger.debug("Checking open ports")
        ports = run_command("netstat -tuln | grep -E '8090|18888|50051'", check=False, shell=True)
        logger.debug(f"Open ports:\n{ports}")
        
        # Try to connect to node API
        try:
            logger.debug("Trying to connect to node API")
            print("Attempting to connect to node API (may not work immediately)...")
            
            api_response = run_command("curl -s http://127.0.0.1:8090/wallet/getnodeinfo", check=False)
            logger.debug(f"API response:\n{api_response}")
            
            if api_response and len(api_response) > 10:  # Some response received
                print_success("Node is responding to API requests!")
                logger.debug("Node is responding to API requests")
            else:
                print_warning("Node is not yet responding to API requests. This is normal if it was just started.")
                logger.warning("Node is not yet responding to API requests")
        except Exception as e:
            logger.warning(f"Error connecting to API: {str(e)}")
            print_warning(f"Error connecting to API: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error checking node status: {str(e)}")
        logger.error(traceback.format_exc())
        print_error(f"Error checking node status: {str(e)}")

def main():
    """Main function of the script."""
    try:
        start_time = time.time()
        logger.info("==========================================")
        logger.info("   TRON Lite Full Node Installation      ")
        logger.info("==========================================")
        
        print(f"{GREEN}===========================================")
        print(f"   TRON Lite Full Node Installation   ")
        print(f"==========================================={RESET}")
        print(f"Installation logs: {LOG_FILE}")
        
        # Check root privileges
        check_root()
        
        # Check system resources
        check_system_resources()
        
        # Install dependencies
        install_dependencies()
        
        # Configure Java 8
        configure_java()
        
        # Clone and build java-tron
        clone_and_build_java_tron()
        
        # Download and extract database archive
        download_and_extract_db()
        
        # Create configuration files
        create_config_files()
        
        # Configure autostart
        setup_systemd()
        
        # Start node
        start_node()
        
        # Check node status
        check_node_status()
        
        end_time = time.time()
        installation_time = end_time - start_time
        logger.info(f"Installation completed in {installation_time:.2f} seconds")
        
        print(f"\n{GREEN}===========================================")
        print(f"   TRON Lite Full Node successfully installed!   ")
        print(f"==========================================={RESET}")
        print(f"\nDocumentation can be found in: {TRON_DIR}/README.md")
        print(f"Installation log: {LOG_FILE}")
        print(f"To check node status run: systemctl status tron-node")
        print(f"To view logs run: journalctl -u tron-node -f")
        print(f"Installation completed in {installation_time:.2f} seconds")
    
    except Exception as e:
        logger.critical(f"Critical error during installation: {str(e)}")
        logger.critical(traceback.format_exc())
        print_error(f"Critical error during installation: {str(e)}")
        print(f"See detailed logs: {LOG_FILE}")
        sys.exit(1)

if __name__ == "__main__":
    main()
