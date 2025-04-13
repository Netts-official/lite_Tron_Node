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
import argparse
import glob

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

# Base URL for downloading archive
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

def run_command(command, check=True, shell=False, cwd=None):
    """Run command and return output."""
    logger.debug(f"Running command: {command}")
    try:
        if isinstance(command, str) and not shell:
            command = command.split()
        
        result = subprocess.run(
            command, 
            cwd=cwd,
            check=check, 
            shell=shell, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        logger.debug(f"Command stdout: {result.stdout}")
        logger.debug(f"Command stderr: {result.stderr}")
        
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution error: {command}")
        logger.error(f"Stderr: {e.stderr}")
        print_error(f"Command execution error: {command}")
        print(f"Stderr: {e.stderr}")
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

def check_root():
    """Check for root privileges."""
    logger.debug("Checking for root privileges")
    if os.geteuid() != 0:
        logger.error("Script requires root privileges")
        print_error("This script requires root privileges (sudo).")
        sys.exit(1)
    logger.debug("Root privileges confirmed")

def detect_java_home():
    """Detect Java home directory."""
    print_step("Detecting Java home directory...")
    
    # Try using the readlink command to find the real Java path
    java_path = run_command("readlink -f $(which java)", shell=True, check=False)
    if java_path:
        # Remove '/bin/java' from the path
        java_home = os.path.dirname(os.path.dirname(java_path))
        if os.path.exists(java_home) and os.path.exists(os.path.join(java_home, "bin", "java")):
            print_success(f"Found Java home at: {java_home}")
            return java_home
    
    # Try standard locations
    standard_paths = [
        "/usr/lib/jvm/java-8-openjdk-amd64",
        "/usr/lib/jvm/java-1.8.0-openjdk-amd64",
        "/usr/lib/jvm/java-8-oracle",
        "/usr/lib/jvm/default-java"
    ]
    
    for path in standard_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "bin", "java")):
            print_success(f"Found Java home at: {path}")
            return path
    
    # Fallback to default
    print_warning("Could not detect Java home directory. Using default path.")
    return "/usr/lib/jvm/java-8-openjdk-amd64"

def install_dependencies():
    """Install necessary dependencies."""
    print_step("Installing necessary packages...")
    
    try:
        # Update package lists
        run_command("apt update")
        
        # Install required packages
        run_command("apt install -y git wget curl openjdk-8-jdk maven aria2 axel")
        
        # Check installation of key packages
        for package in ["git", "wget", "curl", "java", "aria2c", "axel"]:
            cmd = f"which {package}"
            if package == "java":
                cmd = "which java"
            elif package == "aria2c":
                cmd = "which aria2c"
            
            path = run_command(cmd, check=False)
            if path:
                print_success(f"Found {package} at: {path}")
            else:
                print_warning(f"Could not find {package}. Some functionality may be limited.")
        
        print_success("All required packages installed")
    
    except Exception as e:
        logger.error(f"Error installing dependencies: {str(e)}")
        print_error(f"Error installing dependencies: {str(e)}")
        print_warning("Continuing anyway, but installation may fail.")

def configure_java():
    """Configure Java 8 as the main version."""
    print_step("Configuring Java 8...")
    
    # Set JAVA_HOME environment variable
    java_home = detect_java_home()
    os.environ["JAVA_HOME"] = java_home
    
    # Export JAVA_HOME globally
    with open("/etc/profile.d/java.sh", "w") as f:
        f.write(f'export JAVA_HOME="{java_home}"\n')
        f.write('export PATH="$JAVA_HOME/bin:$PATH"\n')
    
    # Set Java 8 as default
    try:
        # Find the Java 8 binary
        java8_path = os.path.join(java_home, "bin", "java")
        javac8_path = os.path.join(java_home, "bin", "javac")
        
        if os.path.exists(java8_path):
            run_command(f"update-alternatives --set java {java8_path}", check=False)
        else:
            print_warning(f"Java binary not found at {java8_path}")
        
        if os.path.exists(javac8_path):
            run_command(f"update-alternatives --set javac {javac8_path}", check=False)
        else:
            print_warning(f"Javac binary not found at {javac8_path}")
        
        # Verify Java version
        java_version = run_command("java -version 2>&1", check=False, shell=True)
        logger.debug(f"Java version: {java_version}")
        
        if "1.8" in java_version:
            print_success("Java 8 configured as main version")
        else:
            print_warning("Java version is not 8. This may cause issues.")
    
    except Exception as e:
        logger.error(f"Error configuring Java: {str(e)}")
        print_warning(f"Error configuring Java: {str(e)}")
        print_warning("Continuing anyway, but build might fail.")

def find_latest_backup_url():
    """Find URL of the latest available backup."""
    ARCHIVE_NAME = "LiteFullNode_output-directory.tgz"
    
    print_step("Searching for the latest available backup...")
    
    try:
        # Get page content
        response = requests.get(BASE_URL, timeout=10)
        response.raise_for_status()
        
        # Find backup directories
        backup_dirs = re.findall(r'href="(backup\d{8})/"', response.text)
        
        if not backup_dirs:
            print_warning("No backup directories found. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        # Get latest backup
        latest_backup = sorted(backup_dirs)[-1]
        print_success(f"Found latest backup: {latest_backup}")
        
        # Form download URL
        download_url = f"{BASE_URL}{latest_backup}/{ARCHIVE_NAME}"
        
        # Check availability
        test_response = requests.head(download_url, timeout=10)
        if test_response.status_code != 200:
            print_warning(f"File {download_url} is not available. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        return download_url
    
    except Exception as e:
        print_warning(f"Error finding latest backup: {str(e)}. Using default value.")
        return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"

def download_db_with_aria2(download_url, archive_path, connections=10):
    """Download database using aria2."""
    try:
        print_step(f"Downloading with aria2 using {connections} connections...")
        
        # Ensure temp directory exists
        os.makedirs("/tmp", exist_ok=True)
        
        # Use aria2c with specified connections
        download_cmd = f"cd /tmp && aria2c -x{connections} -s{connections} --file-allocation=none '{download_url}' -o $(basename '{archive_path}')"
        run_command(download_cmd, shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error downloading with aria2: {str(e)}")
        print_warning(f"Error downloading with aria2: {str(e)}")
        return False

def download_db_with_axel(download_url, archive_path, connections=10):
    """Download database using axel."""
    try:
        print_step(f"Downloading with axel using {connections} connections...")
        
        # Ensure temp directory exists
        os.makedirs("/tmp", exist_ok=True)
        
        # Use axel with specified connections
        download_cmd = f"cd /tmp && axel -n {connections} -a '{download_url}' -o $(basename '{archive_path}')"
        run_command(download_cmd, shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error downloading with axel: {str(e)}")
        print_warning(f"Error downloading with axel: {str(e)}")
        return False

def download_db_with_wget(download_url, archive_path):
    """Download database using wget."""
    try:
        print_step("Downloading with wget...")
        
        # Ensure temp directory exists
        os.makedirs("/tmp", exist_ok=True)
        
        # Use wget as a fallback
        download_cmd = f"cd /tmp && wget -O $(basename '{archive_path}') '{download_url}'"
        run_command(download_cmd, shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error downloading with wget: {str(e)}")
        print_warning(f"Error downloading with wget: {str(e)}")
        return False

def find_archive_file(expected_path):
    """Find the archive file in various possible locations."""
    if os.path.exists(expected_path):
        return expected_path
    
    # Check alternative locations
    basename = os.path.basename(expected_path)
    alt_paths = [
        os.path.join("/tmp", basename),
        os.path.join(TRON_DIR, basename),
        os.path.join(TRON_DIR, "tmp", basename),
        os.path.join(os.getcwd(), basename),
    ]
    
    # Also search for similar files in /tmp
    alt_paths.extend(glob.glob(f"/tmp/*{basename}*"))
    
    for path in alt_paths:
        if os.path.exists(path):
            print_success(f"Found archive at {path}")
            return path
    
    print_error(f"Archive not found in any location.")
    return None

def extract_with_tar_command(archive_path, output_dir, nested=False):
    """Extract archive using tar command."""
    try:
        if nested:
            print_step("Extracting with tar command (strip-components)...")
            # Use strip-components to handle nested directories
            run_command(f"tar -xzf {archive_path} --strip-components=1 -C {output_dir}", shell=True)
        else:
            print_step("Extracting with tar command...")
            run_command(f"tar -xzf {archive_path} -C {output_dir}", shell=True)
        
        return True
    except Exception as e:
        logger.error(f"Error extracting with tar command: {str(e)}")
        print_warning(f"Error extracting with tar command: {str(e)}")
        return False

def extract_with_python(archive_path, output_dir):
    """Extract archive using Python's tarfile."""
    try:
        print_step("Extracting with Python tarfile...")
        with tarfile.open(archive_path) as tar:
            # Get all top-level directories in archive
            top_dirs = set()
            for member in tar.getmembers():
                parts = member.name.split('/')
                if parts:
                    top_dirs.add(parts[0])
            
            logger.debug(f"Top level directories in archive: {top_dirs}")
            
            # Check if there's a nested output-directory
            if 'output-directory' in top_dirs:
                print_warning("Archive contains nested output-directory, adjusting extraction")
                
                # Create a temporary directory for extraction
                tmp_extract_dir = f"/tmp/tron_extract_{int(time.time())}"
                os.makedirs(tmp_extract_dir, exist_ok=True)
                
                tar.extractall(path=tmp_extract_dir)
                
                # Move database from nested structure to correct location
                nested_db_path = os.path.join(tmp_extract_dir, 'output-directory', 'database')
                if os.path.exists(nested_db_path):
                    print_success(f"Moving database from {nested_db_path} to {output_dir}")
                    if os.path.exists(os.path.join(output_dir, 'database')):
                        shutil.rmtree(os.path.join(output_dir, 'database'))
                    shutil.move(nested_db_path, output_dir)
                
                # Cleanup temp directory
                shutil.rmtree(tmp_extract_dir, ignore_errors=True)
            else:
                # Normal extraction
                tar.extractall(path=output_dir)
        
        return True
    except Exception as e:
        logger.error(f"Error extracting with Python tarfile: {str(e)}")
        print_warning(f"Error extracting with Python tarfile: {str(e)}")
        return False

def download_and_extract_db():
    """Download and extract database archive with multi-threaded download."""
    print_step("Preparing to download and extract database...")
    
    # Clean up existing output directory to avoid duplication issues
    if os.path.exists(OUTPUT_DIR):
        print_warning(f"Removing existing output directory at {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    
    # Create fresh output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get download URL
    download_url = find_latest_backup_url()
    print(f"Download URL: {download_url}")
    
    # Archive path
    archive_path = f"/tmp/tron_backup.tgz"
    
    # ====== Download section ======
    # Try multiple download methods in order of preference
    success = False
    
    # Check if aria2 is available
    if run_command("which aria2c", check=False):
        success = download_db_with_aria2(download_url, archive_path)
    
    # If aria2 failed, try axel
    if not success and run_command("which axel", check=False):
        success = download_db_with_axel(download_url, archive_path)
    
    # If both failed, fall back to wget
    if not success:
        success = download_db_with_wget(download_url, archive_path)
    
    if not success:
        print_error("All download methods failed. Cannot continue.")
        sys.exit(1)
    
    print_success("Archive downloaded")
    
    # ====== Find archive file ======
    archive_path = find_archive_file(archive_path)
    if not archive_path:
        print_error("Could not find downloaded archive. Installation cannot continue.")
        sys.exit(1)
    
    # ====== Extract section ======
    print_step("Extracting database archive...")
    
    # Determine if archive has nested structure
    has_nested_structure = False
    try:
        with tarfile.open(archive_path) as tar:
            top_dirs = set()
            for member in tar.getmembers():
                parts = member.name.split('/')
                if parts:
                    top_dirs.add(parts[0])
            has_nested_structure = 'output-directory' in top_dirs
            logger.debug(f"Archive has nested structure: {has_nested_structure}")
    except Exception as e:
        logger.warning(f"Could not check archive structure: {str(e)}")
    
    # Try multiple extraction methods in order of preference
    extraction_success = False
    
    # Try tar command first (more efficient for large files)
    extraction_success = extract_with_tar_command(archive_path, OUTPUT_DIR, nested=has_nested_structure)
    
    # If tar command failed, try Python's tarfile
    if not extraction_success:
        extraction_success = extract_with_python(archive_path, OUTPUT_DIR)
    
    if not extraction_success:
        print_error("All extraction methods failed. Cannot continue.")
        sys.exit(1)
    
    print_success("Archive extraction completed")
    
    # ====== Verify database directory ======
    db_path = os.path.join(OUTPUT_DIR, 'database')
    if not os.path.exists(db_path):
        print_warning("Database directory not found at expected location. Searching...")
        
        # Try to find database directory
        found = False
        for root, dirs, files in os.walk(OUTPUT_DIR):
            if 'database' in dirs:
                src_path = os.path.join(root, 'database')
                print_success(f"Found database at {src_path}, moving to correct location")
                
                # Remove target if it exists
                if os.path.exists(db_path):
                    shutil.rmtree(db_path)
                
                # Move to correct location
                shutil.move(src_path, OUTPUT_DIR)
                found = True
                break
        
        if not found:
            print_error("Database directory not found after extraction. Installation cannot continue.")
            sys.exit(1)
    
    # ====== Clean up archive ======
    try:
        if os.path.exists(archive_path):
            os.remove(archive_path)
            print_success(f"Removed archive file: {archive_path}")
    except Exception as e:
        print_warning(f"Could not remove archive file: {str(e)}")

def clone_and_build_java_tron():
    """Clone and build java-tron."""
    print_step("Cloning and building java-tron...")
    
    # Check if directory exists
    if os.path.exists(TRON_DIR):
        print_warning(f"Directory {TRON_DIR} already exists. Removing it for clean installation.")
        shutil.rmtree(TRON_DIR, ignore_errors=True)
    
    # Create directory
    os.makedirs(TRON_DIR, exist_ok=True)
    
    # Clone repository
    run_command(f"git clone https://github.com/tronprotocol/java-tron.git {TRON_DIR}")
    
    # Change to directory
    os.chdir(TRON_DIR)
    
    # Checkout master branch
    run_command("git fetch")
    run_command("git checkout -t origin/master", check=False)
    
    # Fix build.gradle file
    gradle_build_file = f"{TRON_DIR}/build.gradle"
    if os.path.exists(gradle_build_file):
        with open(gradle_build_file, "a") as f:
            f.write("\n\nallprojects {\n    dependencies {\n        compile 'javax.annotation:javax.annotation-api:1.3.2'\n    }\n}\n")
    
    # Set gradlew permissions
    gradlew_path = f"{TRON_DIR}/gradlew"
    if os.path.exists(gradlew_path):
        os.chmod(gradlew_path, os.stat(gradlew_path).st_mode | stat.S_IEXEC)
    
    # Build project
    print("Building java-tron (this may take 10-20 minutes)...")
    
    # Export JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", detect_java_home())
    build_cmd = f"JAVA_HOME={java_home} ./gradlew clean build -x test"
    
    # Run the build command
    build_result = subprocess.run(build_cmd, shell=True, cwd=TRON_DIR)
    
    # Check build success
    if build_result.returncode != 0 or not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
        print_error("java-tron build failed")
        
        # Try fallback approach
        print_warning("Trying fallback approach...")
        
        # Download annotation jar
        lib_dir = f"{TRON_DIR}/lib"
        os.makedirs(lib_dir, exist_ok=True)
        annotation_jar = f"{lib_dir}/javax.annotation-api-1.3.2.jar"
        run_command(f"wget -O {annotation_jar} https://repo1.maven.org/maven2/javax/annotation/javax.annotation-api/1.3.2/javax.annotation-api-1.3.2.jar", shell=True)
        
        # Update build.gradle
        with open(gradle_build_file, "a") as f:
            f.write(f"\n\nallprojects {{\n    dependencies {{\n        compile files('{lib_dir}/javax.annotation-api-1.3.2.jar')\n    }}\n}}\n")
        
        # Try build again
        print("Retrying build with fallback approach...")
        build_result = subprocess.run(build_cmd, shell=True, cwd=TRON_DIR)
        
        if build_result.returncode != 0 or not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
            print_error("Build failed again. Installation cannot continue.")
            sys.exit(1)
    
    # Verify FullNode.jar was created
    jar_path = f"{TRON_DIR}/build/libs/FullNode.jar"
    if os.path.exists(jar_path):
        jar_size = os.path.getsize(jar_path) // (1024 * 1024)  # Size in MB
        print_success(f"java-tron built successfully. FullNode.jar size: {jar_size} MB")
    else:
        print_error("FullNode.jar not found. Build may have failed.")
        sys.exit(1)

def setup_vscode_optimization():
    """Set up VSCode optimization."""
    print_step("Setting up VSCode optimization...")
    
    # Create .vscode directory
    os.makedirs(VSCODE_SETTINGS_DIR, exist_ok=True)
    
    # VSCode settings
    vscode_settings = {
        "files.watcherExclude": {
            "**/output-directory/**": True,
            "**/database/**": True,
            "**/index/**": True
        },
        "files.exclude": {
            "**/output-directory/**": True,
            "**/database/**": True,
            "**/index/**": True
        },
        "search.exclude": {
            "**/output-directory/**": True,
            "**/database/**": True,
            "**/index/**": True
        },
        "java.import.exclusions": [
            "**/output-directory/**",
            "**/database/**",
            "**/index/**"
        ],
        "java.configuration.updateBuildConfiguration": "disabled",
        "java.autobuild.enabled": False
    }
    
    # Write settings file
    with open(VSCODE_SETTINGS_FILE, "w") as f:
        json.dump(vscode_settings, f, indent=2)
    
    # Create .gitignore to exclude large directories
    gitignore_content = """# Node databases
/output-directory/
/database/
/index/

# Build outputs
/build/
/lib/

# Logs
*.log

# VSCode
.vscode/
"""
    # Write .gitignore
    with open(f"{TRON_DIR}/.gitignore", "w") as f:
        f.write(gitignore_content)
    
    print_success("VSCode optimization configured")

def create_config_files():
    """Create configuration files."""
    print_step("Setting up configuration files...")
    
    # Copy existing config file if it exists
    src_config = f"{SCRIPT_DIR}/last-conf.conf"
    if os.path.exists(src_config):
        shutil.copy2(src_config, CONFIG_FILE)
        print_success("Copied existing configuration file")
    else:
        print_warning("Configuration file not found. Please create last-conf.conf manually.")
    
    # Create startup script
    start_script_content = """#!/bin/bash
java -Xmx24g -XX:+UseConcMarkSweepGC -jar /home/java-tron/build/libs/FullNode.jar -c /home/java-tron/last-conf.conf -d /home/java-tron/output-directory/
"""
    with open(START_SCRIPT, "w") as f:
        f.write(start_script_content)
    
    # Set execute permissions
    os.chmod(START_SCRIPT, os.stat(START_SCRIPT).st_mode | stat.S_IEXEC)
    
    # Create systemd service
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
    with open(SYSTEMD_SERVICE, "w") as f:
        f.write(systemd_service_content)
    
    # Create README.md
    readme_path = f"{TRON_DIR}/README.md"
    with open(readme_path, "w") as f:
        f.write("# TRON Lite Full Node\n\n")
        f.write("This TRON Lite Full Node was automatically installed via the installation script.\n\n")
        f.write("## System Requirements\n\n")
        f.write("- Ubuntu 20.04/22.04 or Debian 10/11\n")
        f.write("- Minimum 16GB RAM (24GB recommended)\n")
        f.write("- Minimum 500GB SSD storage space\n")
        f.write("- Good internet connection (10+ Mbps)\n\n")
        f.write("## Basic Commands\n\n")
        f.write("### Node Management\n\n")
        f.write("#### Check Node Status\n```bash\nsystemctl status tron-node\n```\n\n")
        f.write("#### Start Node\n```bash\nsystemctl start tron-node\n```\n\n")
        f.write("#### Stop Node\n```bash\nsystemctl stop tron-node\n```\n\n")
        f.write("#### Restart Node\n```bash\nsystemctl restart tron-node\n```\n\n")
        f.write("#### Enable Autostart\n```bash\nsystemctl enable tron-node\n```\n\n")
        f.write("### Monitoring\n\n")
        f.write("#### Check Running Processes\n```bash\nps aux | grep [F]ullNode\n```\n\n")
        f.write("#### Check Node Information\n```bash\ncurl http://127.0.0.1:8090/wallet/getnodeinfo\n```\n\n")
        f.write("#### Check Current Block\n```bash\ncurl http://127.0.0.1:8090/wallet/getnowblock\n```\n\n")
        f.write("#### View Logs\n```bash\njournalctl -u tron-node -f\n```\n\n")
        f.write("#### View Last 100 Log Lines\n```bash\njournalctl -u tron-node -n 100\n```\n\n")
        f.write("#### View Logs for the Last Hour\n```bash\njournalctl -u tron-node --since \"1 hour ago\"\n```\n\n")
        f.write("### Manual Control\n\n")
        f.write("#### Manual Node Start (if needed)\n```bash\ncd /home/java-tron\nchmod +x last-node-start.sh\nnohup bash last-node-start.sh &> /dev/null &\n```\n\n")
        f.write("## Troubleshooting\n\n")
        f.write("### Node Not Starting\n1. Check system resources: `free -h` and `df -h`\n")
        f.write("2. Check logs: `journalctl -u tron-node -n 100`\n")
        f.write("3. Verify Java version: `java -version` (should be 1.8.x)\n")
        f.write("4. Check configuration file for errors\n\n")
        f.write("### Synchronization Issues\n1. Verify network connectivity\n")
        f.write("2. Check if your port 18888 is open for external connections\n")
        f.write("3. Monitor sync progress: `curl http://127.0.0.1:8090/wallet/getnodeinfo | grep block`\n")
        f.write("4. Try restarting the node: `systemctl restart tron-node`\n\n")
    
    print_success("Configuration files created")

def setup_systemd():
    """Configure autostart via systemd."""
    print_step("Setting up autostart via systemd...")
    
    # Reload systemd
    run_command("systemctl daemon-reload")
    
    # Enable autostart
    run_command("systemctl enable tron-node")
    
    print_success("Autostart configured")

def start_node():
    """Start the node."""
    print_step("Starting TRON node...")
    
    # Start service
    run_command("systemctl start tron-node")
    
    # Wait for startup
    time.sleep(5)
    
    # Check status
    status = run_command("systemctl is-active tron-node", check=False)
    
    if status == "active":
        print_success("TRON node started successfully!")
    else:
        print_warning("TRON node is starting, check status in a few minutes.")
    
    # Node will continue to run in background

def cleanup_installation_files():
    """Clean up installation files."""
    print_step("Cleaning up installation files...")
    
    # Files to clean up
    cleanup_files = [
        f"{SCRIPT_DIR}/install_tron_node.py",
        f"{SCRIPT_DIR}/installation.log",
        f"{SCRIPT_DIR}/install.py",
        f"{SCRIPT_DIR}/fixed_installer.py",
        f"{SCRIPT_DIR}/working-installer.py"
    ]
    
    # Remove each file if it exists
    for file_path in cleanup_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Removed file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {str(e)}")
    
    # Move logs to permanent location
    try:
        src_log = LOG_FILE
        dst_log = "/var/log/tron-installation.log"
        if os.path.exists(src_log):
            shutil.copy2(src_log, dst_log)
            print_success(f"Installation log copied to {dst_log}")
    except Exception as e:
        print_warning(f"Failed to move log file: {str(e)}")
    
    print_success("Installation files cleaned up")

def run_as_daemon():
    """Fork the process and run in background."""
    print("Starting TRON node installation in background mode...")
    
    # Test log file access
    log_file = '/var/log/tron-background-install.log'
    try:
        with open(log_file, 'a') as test:
            test.write("Testing log file access...\n")
    except PermissionError:
        # Fall back to home directory if /var/log is not writable
        log_file = os.path.join(HOME_DIR, 'tron-background-install.log')
        print(f"Cannot write to /var/log, using {log_file} instead")
    
    try:
        # Double fork to prevent zombie processes
        pid = os.fork()
        if pid > 0:  # First parent
            # Exit first parent
            sys.exit(0)
    except OSError as e:
        print_error(f"Fork #1 failed: {e}")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)
    
    try:
        # Second fork
        pid = os.fork()
        if pid > 0:  # Second parent
            # Exit second parent
            print(f"Daemon process started with PID {pid}")
            print("Installation will continue in background.")
            print(f"Check progress with: tail -f {log_file}")
            sys.exit(0)
    except OSError as e:
        print_error(f"Fork #2 failed: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open(log_file, 'a+') as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())

def main():
    """Main installation function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="TRON Lite Full Node Installer")
    parser.add_argument("--background", action="store_true", help="Continue installation in background mode")
    args = parser.parse_args()
    
    # If background flag is specified, run as daemon
    if args.background and os.environ.get("TRON_DAEMON") != "1":
        os.environ["TRON_DAEMON"] = "1"
        run_as_daemon()
        return
    
    try:
        start_time = time.time()
        print(f"{GREEN}===========================================")
        print(f"   TRON Lite Full Node Installation   ")
        print(f"==========================================={RESET}")
        
        # Check root
        check_root()
        
        # Install dependencies
        install_dependencies()
        
        # Configure Java
        configure_java()
        
        # Changed order: download and extract database first, then build
        # This ensures we don't waste time building if download fails
        download_and_extract_db()
        
        # Clone and build java-tron
        clone_and_build_java_tron()
        
        # Configure VSCode
        setup_vscode_optimization()
        
        # Create config files
        create_config_files()
        
        # Setup systemd
        setup_systemd()
        
        # Start node
        start_node()
        
        # Cleanup
        cleanup_installation_files()
        
        end_time = time.time()
        installation_time = end_time - start_time
        
        print(f"\n{GREEN}===========================================")
        print(f"   TRON Lite Full Node successfully installed!   ")
        print(f"==========================================={RESET}")
        print(f"\nDocumentation: {TRON_DIR}/README.md")
        print(f"Installation log: /var/log/tron-installation.log")
        print(f"Check status: systemctl status tron-node")
        print(f"View logs: journalctl -u tron-node -f")
        print(f"Installation completed in {installation_time:.2f} seconds")
        
    except Exception as e:
        print_error(f"Critical error during installation: {str(e)}")
        logger.error(f"Critical error: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
