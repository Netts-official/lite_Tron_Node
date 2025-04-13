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

# Base URLs for downloading archive
PRIMARY_SERVER = "http://34.86.86.229/"
SECONDARY_SERVER = "http://34.143.247.77/"
FALLBACK_URL = "http://34.86.86.229/backup20250410/LiteFullNode_output-directory.tgz"

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

def find_latest_backup_url(server_url):
    """Find URL of the latest available backup on the specified server."""
    ARCHIVE_NAME = "LiteFullNode_output-directory.tgz"
    
    print_step(f"Searching for the latest available backup on {server_url}...")
    
    try:
        # Get page content
        response = requests.get(server_url, timeout=10)
        response.raise_for_status()
        
        # Find backup directories
        backup_dirs = re.findall(r'href="(backup\d{8})/"', response.text)
        
        if not backup_dirs:
            print_warning(f"No backup directories found on {server_url}.")
            return None
        
        # Get latest backup
        latest_backup = sorted(backup_dirs)[-1]
        print_success(f"Found latest backup: {latest_backup}")
        
        # Form download URL
        download_url = f"{server_url}{latest_backup}/{ARCHIVE_NAME}"
        
        # Check availability
        test_response = requests.head(download_url, timeout=10)
        if test_response.status_code != 200:
            print_warning(f"File {download_url} is not available.")
            return None
        
        return download_url
    
    except Exception as e:
        print_warning(f"Error finding latest backup on {server_url}: {str(e)}")
        return None

def download_with_aria2(download_url, archive_path, connections=10):
    """Download using aria2 with multiple connections."""
    print_step(f"Attempting to download with aria2 ({connections} connections)...")
    
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(archive_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Run aria2c command
        download_cmd = f"cd {output_dir} && aria2c -x{connections} -s{connections} --file-allocation=none '{download_url}' -o '{os.path.basename(archive_path)}'"
        run_command(download_cmd, shell=True)
        
        # Check if file exists
        if os.path.exists(archive_path):
            file_size = os.path.getsize(archive_path) / (1024 * 1024)  # Size in MB
            print_success(f"Download completed. File size: {file_size:.2f} MB")
            return True
        else:
            print_warning(f"Download completed but file not found at {archive_path}")
            return False
    
    except Exception as e:
        logger.error(f"Error downloading with aria2: {str(e)}")
        print_warning(f"Failed to download with aria2: {str(e)}")
        return False

def download_with_wget(download_url, archive_path):
    """Download using wget (single connection)."""
    print_step("Attempting to download with wget (single connection)...")
    
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(archive_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Run wget command
        download_cmd = f"wget -O '{archive_path}' '{download_url}'"
        run_command(download_cmd, shell=True)
        
        # Check if file exists
        if os.path.exists(archive_path):
            file_size = os.path.getsize(archive_path) / (1024 * 1024)  # Size in MB
            print_success(f"Download completed. File size: {file_size:.2f} MB")
            return True
        else:
            print_warning(f"Download completed but file not found at {archive_path}")
            return False
    
    except Exception as e:
        logger.error(f"Error downloading with wget: {str(e)}")
        print_warning(f"Failed to download with wget: {str(e)}")
        return False

def download_and_extract_db():
    """Download and extract database archive with multi-server fallback."""
    print_step("Preparing to download and extract database...")
    
    # Clean up existing output directory to avoid duplication issues
    if os.path.exists(OUTPUT_DIR):
        print_warning(f"Removing existing output directory at {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    
    # Create fresh output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Define archive path
    archive_path = "/tmp/tron_backup.tgz"
    
    # Remove any existing archive file (from previous attempts)
    if os.path.exists(archive_path):
        try:
            os.remove(archive_path)
            print_warning(f"Removed existing archive file: {archive_path}")
        except Exception as e:
            print_warning(f"Could not remove existing archive: {str(e)}")
    
    # ====== First try: Primary server with aria2 ======
    download_success = False
    
    # Try to get latest backup URL from primary server
    primary_url = find_latest_backup_url(PRIMARY_SERVER)
    if primary_url:
        print_step(f"Attempting to download from primary server: {primary_url}")
        download_success = download_with_aria2(primary_url, archive_path)
    
    # ====== Second try: Secondary server with aria2 ======
    if not download_success:
        print_warning("Download from primary server failed. Trying secondary server...")
        secondary_url = find_latest_backup_url(SECONDARY_SERVER)
        if secondary_url:
            print_step(f"Attempting to download from secondary server: {secondary_url}")
            download_success = download_with_aria2(secondary_url, archive_path)
    
    # ====== Third try: Fallback URL with wget ======
    if not download_success:
        print_warning("Download from both servers failed. Using fallback URL with wget...")
        download_success = download_with_wget(FALLBACK_URL, archive_path)
    
    # Check if download was successful
    if not download_success or not os.path.exists(archive_path):
        print_error("All download attempts failed. Installation cannot continue.")
        sys.exit(1)
    
    print_success("Archive successfully downloaded")
    
    # ====== Extract archive ======
    print_step("Extracting database archive...")
    
    try:
        # Verify archive exists
        if not os.path.exists(archive_path):
            print_error(f"Archive file not found at {archive_path}. Extraction failed.")
            sys.exit(1)
        
        # Check archive structure
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
                print_warning("Archive contains nested output-directory, using strip-components method")
                tar.close()  # Close tarfile before using system tar command
                
                # Use tar command with strip-components option
                extract_cmd = f"tar -xzf '{archive_path}' --strip-components=1 -C '{OUTPUT_DIR}'"
                run_command(extract_cmd, shell=True)
            else:
                # Normal extraction
                print_step("Extracting archive normally...")
                tar.extractall(path=OUTPUT_DIR)
    
    except Exception as e:
        print_error(f"Error during extraction: {str(e)}")
        logger.error(f"Extraction error: {traceback.format_exc()}")
        
        # Fallback to direct extraction
        print_warning("Falling back to direct extraction")
        try:
            extract_cmd = f"tar -xzf '{archive_path}' -C '{OUTPUT_DIR}'"
            run_command(extract_cmd, shell=True)
        except Exception as e2:
            print_error(f"Fatal error during extraction: {str(e2)}")
            sys.exit(1)
    
    print_success("Archive extraction completed")
    
    # Verify database directory exists
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
    else:
        print_success(f"Database directory found at {db_path}")
    
    # Remove archive
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
