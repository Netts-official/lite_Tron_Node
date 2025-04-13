# TRON Lite Full Node Deployment Script

## Description

This script is designed for automatic deployment of a TRON Lite Full Node on Ubuntu/Debian servers. The script performs the following operations:

1. Installation of necessary dependencies
2. Configuration of Java 8 as the main version
3. Cloning and building the java-tron repository
4. Automatic search and download of the latest available database archive for quick start
5. Creation of all configuration files
6. Setup of autostart via systemd
7. Starting the node

## Requirements

- Ubuntu 20.04/22.04 or Debian 10/11
- Minimum 16 GB RAM (24 GB recommended)
- Minimum 500 GB disk space (SSD recommended)
- Root privileges for installation

## Installation

### Option 1: Direct installation from GitHub

```bash
# Clone the repository
git clone https://github.com/Netts-official/lite_Tron_Node.git
cd lite_Tron_Node

# Make the script executable
chmod +x install_tron_node.py

# Run the script with root privileges
sudo python3 install_tron_node.py
```

### Option 2: Download and run the script directly

```bash
# Download the script
wget https://raw.githubusercontent.com/Netts-official/lite_Tron_Node/main/install_tron_node.py

# Make the script executable
chmod +x install_tron_node.py

# Run the script with root privileges
sudo python3 install_tron_node.py
```

## Node Management Commands

### Check node status
```bash
systemctl status tron-node
```

### Start the node
```bash
systemctl start tron-node
```

### Stop the node
```bash
systemctl stop tron-node
```

### Restart the node
```bash
systemctl restart tron-node
```

### Enable autostart
```bash
systemctl enable tron-node
```

### Check running processes
```bash
ps aux | grep [F]ullNode
```

### Check node information
```bash
curl http://127.0.0.1:8090/wallet/getnodeinfo
```

### Check current block
```bash
curl http://127.0.0.1:8090/wallet/getnowblock
```

## Monitoring and Logs

### View node logs
```bash
journalctl -u tron-node -f
```

### View last 100 log lines
```bash
journalctl -u tron-node -n 100
```

### View logs for the last hour
```bash
journalctl -u tron-node --since "1 hour ago"
```

## Troubleshooting

### Java Version Issues

If you encounter issues with the Java version, you can manually configure Java 8:

```bash
sudo update-alternatives --config java
# Select the option with java-8-openjdk

sudo update-alternatives --config javac
# Select the option with java-8-openjdk
```

### Java-tron Compilation Issues

If you encounter errors during compilation related to the missing `javax.annotation.Generated` class, add the following dependency to the `build.gradle` file:

```
dependencies {
    implementation 'javax.annotation:javax.annotation-api:1.3.2'
}
```

### Database Archive Download Issues

If the script fails to automatically find or download the latest database archive, you can:

1. Manually check available backups:
```bash
curl -s http://34.86.86.229/ | grep -o 'backup[0-9]\{8\}'
```

2. Download the archive manually using the latest available backup (replace XXXXXXXX with the actual date):
```bash
wget http://34.86.86.229/backupXXXXXXXX/LiteFullNode_output-directory.tgz -O /tmp/LiteFullNode_output-directory.tgz
mkdir -p /home/java-tron/output-directory
tar -xzf /tmp/LiteFullNode_output-directory.tgz -C /home/java-tron/output-directory
```

## Node Update

To update the node to the latest version:

```bash
cd /home/java-tron
git pull
./gradlew clean build -x test
systemctl restart tron-node
```

## Additional Information

- Configuration file: `/home/java-tron/last-conf.conf`
- Startup script: `/home/java-tron/last-node-start.sh`
- Data directory: `/home/java-tron/output-directory`
- Systemd service: `/etc/systemd/system/tron-node.service`

## Useful Links

- [Official TRON Documentation](https://developers.tron.network/)
- [Java-tron GitHub Repository](https://github.com/tronprotocol/java-tron)
- [TRON Explorer](https://tronscan.org/)# lite_Tron_Node
LiteFullNode installation
