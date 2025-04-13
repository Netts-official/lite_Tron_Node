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

def install_dependencies():
    """Install necessary dependencies."""
    print_step("Installing necessary packages...")
    run_command("apt update")
    run_command("apt install -y git wget curl openjdk-8-jdk maven")
    print_success("Packages installed")

def configure_java():
    """Configure Java 8 as the main version."""
    print_step("Configuring Java 8...")
    
    # Set JAVA_HOME environment variable
    java_home = "/usr/lib/jvm/java-8-openjdk-amd64"
    os.environ["JAVA_HOME"] = java_home
    
    # Export JAVA_HOME globally
    with open("/etc/profile.d/java.sh", "w") as f:
        f.write(f'export JAVA_HOME="{java_home}"\n')
        f.write('export PATH="$JAVA_HOME/bin:$PATH"\n')
    
    # Set Java 8 as default
    run_command("update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java", check=False)
    run_command("update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac", check=False)
    
    print_success("Java 8 configured as main version")

def find_latest_backup_url():
    """Find URL of the latest available backup."""
    ARCHIVE_NAME = "LiteFullNode_output-directory.tgz"
    
    print_step("Searching for the latest available backup...")
    
    try:
        # Get page content
        response = requests.get(BASE_URL)
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
        test_response = requests.head(download_url)
        if test_response.status_code != 200:
            print_warning(f"File {download_url} is not available. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        return download_url
    
    except Exception as e:
        print_warning(f"Error finding latest backup: {str(e)}. Using default value.")
        return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"

def download_and_extract_db():
    """Download and extract database archive."""
    print_step("Downloading database archive...")
    
    # Clean up existing output directory to avoid duplication issues
    if os.path.exists(OUTPUT_DIR):
        print_warning(f"Removing existing output directory at {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    
    # Create fresh output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Get download URL
    download_url = find_latest_backup_url()
    print(f"Download URL: {download_url}")
    
    # Download file
    archive_path = f"/tmp/tron_backup.tgz"
    print(f"Downloading {download_url}...")
    
    run_command(f"wget -O {archive_path} {download_url}", shell=True)
    print_success("Archive downloaded")
    
    # Extract archive
    print_step("Extracting database archive...")
    
    try:
        # Check archive structure first
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
                print_warning("Archive contains nested output-directory, adjusting extraction path")
                
                # Create a temporary directory for extraction
                tmp_extract_dir = f"/tmp/tron_extract_{int(time.time())}"
                os.makedirs(tmp_extract_dir, exist_ok=True)
                
                # Extract to temp directory
                tar.extractall(path=tmp_extract_dir)
                
                # Move database from nested structure to correct location
                nested_db_path = os.path.join(tmp_extract_dir, 'output-directory', 'database')
                if os.path.exists(nested_db_path):
                    print(f"Moving database from {nested_db_path} to {OUTPUT_DIR}")
                    shutil.move(nested_db_path, OUTPUT_DIR)
                
                # Cleanup temp directory
                shutil.rmtree(tmp_extract_dir, ignore_errors=True)
            else:
                # Normal extraction
                tar.extractall(path=OUTPUT_DIR)
    
    except Exception as e:
        print_error(f"Error during extraction: {str(e)}")
        logger.error(f"Extraction error: {traceback.format_exc()}")
        
        # Fallback to direct extraction without analysis
        print_warning("Falling back to direct extraction")
        run_command(f"tar -xzf {archive_path} -C {OUTPUT_DIR}", shell=True)
    
    print_success("Archive extracted")
    
    # Verify database directory exists
    db_path = os.path.join(OUTPUT_DIR, 'database')
    if not os.path.exists(db_path):
        print_warning("Database directory not found at expected location. Searching...")
        
        # Try to find database directory
        for root, dirs, files in os.walk(OUTPUT_DIR):
            if 'database' in dirs:
                src_path = os.path.join(root, 'database')
                print(f"Found database at {src_path}, moving to correct location")
                
                # Remove target if it exists
                if os.path.exists(db_path):
                    shutil.rmtree(db_path)
                
                # Move to correct location
                shutil.move(src_path, OUTPUT_DIR)
                break
    
    # Remove archive
    os.remove(archive_path)

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
    print("Build started, output redirected to log file...")
    
    # Export JAVA_HOME
    build_cmd = f"JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 ./gradlew clean build -x test"
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
    
    print_success("java-tron built successfully")

def setup_vscode_optimization():
    """Set up VSCode optimization."""
    print_step("Setting up VSCode optimization...")
    
    # Create .vscode directory
    os.makedirs(VSCODE_SETTINGS_DIR, exist_ok=True)
    
    # VSCode settings - Using Python True instead of JavaScript true
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
        f.write("Node was automatically installed via installation script.\n\n")
        f.write("## Basic Commands\n\n")
        f.write("### Check Node Status\n```bash\nsystemctl status tron-node\n```\n\n")
        f.write("### Start Node\n```bash\nsystemctl start tron-node\n```\n\n")
        f.write("### Stop Node\n```bash\nsystemctl stop tron-node\n```\n\n")
        f.write("### Restart Node\n```bash\nsystemctl restart tron-node\n```\n\n")
        f.write("### Check Running Processes\n```bash\nps aux | grep [F]ullNode\n```\n\n")
        f.write("### Check Node Information\n```bash\ncurl http://127.0.0.1:8090/wallet/getnodeinfo\n```\n\n")
        f.write("### Check Current Block\n```bash\ncurl http://127.0.0.1:8090/wallet/getnowblock\n```\n\n")
        f.write("### View Logs\n```bash\njournalctl -u tron-node -f\n```\n\n")
        f.write("### Manual Node Start (if needed)\n```bash\ncd /home/java-tron\nchmod +x last-node-start.sh\nnohup bash last-node-start.sh &> /dev/null &\n```\n")
    
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
    except Exception as e:
        print_warning(f"Failed to move log file: {str(e)}")
    
    print_success("Installation files cleaned up")

def run_as_daemon():
    """Fork the process and run in background."""
    print("Starting TRON node installation in background mode...")
    
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
            print("Check progress with: tail -f /var/log/tron-background-install.log")
            sys.exit(0)
    except OSError as e:
        print_error(f"Fork #2 failed: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open('/var/log/tron-background-install.log', 'a+') as log:
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
        
        # Clone and build java-tron
        clone_and_build_java_tron()
        
        # Configure VSCode
        setup_vscode_optimization()
        
        # Create config files
        create_config_files()
        
        # Download and extract database
        download_and_extract_db()
        
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
