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
from datetime import datetime

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

# Base URL for downloading archive (actual link will be determined automatically)
BASE_URL = "http://34.86.86.229/"

def print_step(message):
    """Print installation step."""
    print(f"\n{BLUE}==>{RESET} {message}")

def print_success(message):
    """Print success message."""
    print(f"{GREEN}✓ {message}{RESET}")

def print_error(message):
    """Print error message."""
    print(f"{RED}✗ ERROR: {message}{RESET}")
    
def print_warning(message):
    """Print warning message."""
    print(f"{YELLOW}! {message}{RESET}")

def run_command(command, check=True, shell=False):
    """Run command with output result."""
    try:
        if isinstance(command, str) and not shell:
            command = command.split()
        result = subprocess.run(command, check=check, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print_error(f"Command execution error: {command}")
        print(f"Stderr: {e.stderr}")
        if check:
            sys.exit(1)
        return None

def check_root():
    """Check for root privileges."""
    if os.geteuid() != 0:
        print_error("This script requires root privileges (sudo).")
        sys.exit(1)

def install_dependencies():
    """Install required dependencies."""
    print_step("Installing necessary packages...")
    run_command("apt update")
    run_command("apt install -y git wget curl openjdk-8-jdk")
    print_success("Packages installed")

def configure_java():
    """Configure Java 8 as the main version."""
    print_step("Configuring Java 8...")
    
    # Check number of installed Java versions
    result = run_command("update-alternatives --list java", check=False)
    if result and "java-8" in result:
        # Set Java 8 as the main version
        process = subprocess.Popen(
            "update-alternatives --config java",
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Find option number for Java 8
        stdout, _ = process.communicate()
        lines = stdout.strip().split('\n')
        java8_option = None
        
        for line in lines:
            if "java-8" in line:
                parts = line.split()
                if parts and len(parts) > 0:
                    java8_option = parts[0].strip()
        
        if java8_option:
            # Set Java 8 manually via echo
            run_command(f"echo {java8_option} | update-alternatives --config java", shell=True)
            
            # Now configure javac
            process = subprocess.Popen(
                "update-alternatives --config javac",
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, _ = process.communicate()
            lines = stdout.strip().split('\n')
            javac8_option = None
            
            for line in lines:
                if "java-8" in line:
                    parts = line.split()
                    if parts and len(parts) > 0:
                        javac8_option = parts[0].strip()
            
            if javac8_option:
                run_command(f"echo {javac8_option} | update-alternatives --config javac", shell=True)
    
    # Check Java version
    java_version = run_command("java -version", check=False)
    if java_version and "1.8" not in java_version:
        print_warning("Java 8 is not set as the main version. Setting manually...")
        # Set Java 8 as default via update-alternatives
        run_command("update-alternatives --set java /usr/lib/jvm/java-8-openjdk-amd64/jre/bin/java")
        run_command("update-alternatives --set javac /usr/lib/jvm/java-8-openjdk-amd64/bin/javac")
    
    # Check again
    java_version = run_command("java -version 2>&1 | grep version", shell=True)
    if "1.8" in java_version:
        print_success("Java 8 configured as the main version")
    else:
        print_error("Failed to configure Java 8")
        sys.exit(1)

def find_latest_backup_url():
    """Find URL of the latest available backup."""
    BASE_URL = "http://34.86.86.229/"
    ARCHIVE_NAME = "LiteFullNode_output-directory.tgz"
    
    print_step("Searching for the latest available backup...")
    
    try:
        # Get page content
        response = requests.get(BASE_URL)
        response.raise_for_status()
        
        # Use regular expressions to find backup* directories
        import re
        backup_dirs = re.findall(r'href="(backup\d{8})/"', response.text)
        
        if not backup_dirs:
            print_warning("Backup directories not found. Using default value.")
            return f"{BASE_URL}backup20250410/{ARCHIVE_NAME}"
        
        # Sort and take the latest (newest) backup
        latest_backup = sorted(backup_dirs)[-1]
        print_success(f"Found latest backup: {latest_backup}")
        
        # Form full download URL
        download_url = f"{BASE_URL}{latest_backup}/{ARCHIVE_NAME}"
        
        # Check file availability
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
    
    # Get actual download URL
    download_url = find_latest_backup_url()
    print(f"Download URL: {download_url}")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Archive file name
    archive_name = os.path.basename(download_url)
    archive_path = f"/tmp/{archive_name}"
    
    # Download archive with progress indicator
    try:
        print(f"Downloading {download_url}...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        # Get file size if server provides it
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded = 0
        
        with open(archive_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Show progress if total size is known
                    if total_size > 0:
                        done = int(50 * downloaded / total_size)
                        sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {downloaded}/{total_size} bytes ({done*2}%)")
                        sys.stdout.flush()
        
        if total_size > 0:
            sys.stdout.write('\n')
        print_success("Archive successfully downloaded")
    except Exception as e:
        print_error(f"Error downloading archive: {str(e)}")
        sys.exit(1)
    
    # Extract archive
    print_step("Extracting database archive...")
    try:
        with tarfile.open(archive_path) as tar:
            # Check for safe paths during extraction
            for member in tar.getmembers():
                if member.name.startswith(('/')) or '..' in member.name:
                    print_error(f"Unsafe path in archive: {member.name}")
                    sys.exit(1)
            
            # Count total number of files for progress indicator
            total_files = len(tar.getmembers())
            print(f"Extracting {total_files} files...")
            
            # Extract files with progress indicator
            for i, member in enumerate(tar.getmembers(), 1):
                tar.extract(member, path=OUTPUT_DIR)
                # Update progress every 100 files
                if i % 100 == 0 or i == total_files:
                    progress = int(i / total_files * 100)
                    sys.stdout.write(f"\rExtraction: {progress}% ({i}/{total_files} files)")
                    sys.stdout.flush()
            
            sys.stdout.write('\n')
        print_success("Archive successfully extracted")
    except Exception as e:
        print_error(f"Error extracting archive: {str(e)}")
        sys.exit(1)
    
    # Remove archive
    os.remove(archive_path)

def clone_and_build_java_tron():
    """Clone and build java-tron."""
    print_step("Cloning and building java-tron...")
    
    # Check if directory exists
    if os.path.exists(TRON_DIR):
        print_warning(f"Directory {TRON_DIR} already exists. Skipping cloning.")
    else:
        # Create directory if it doesn't exist
        os.makedirs(TRON_DIR, exist_ok=True)
        # Clone repository
        run_command(f"git clone https://github.com/tronprotocol/java-tron.git {TRON_DIR}")
    
    # Navigate to directory and checkout master branch
    os.chdir(TRON_DIR)
    run_command("git checkout -t origin/master", check=False)  # May give an error if branch already exists
    
    # Add dependency for javax.annotation.Generated
    gradle_build_file = f"{TRON_DIR}/build.gradle"
    if os.path.exists(gradle_build_file):
        with open(gradle_build_file, "r") as file:
            content = file.read()
        
        # Check if dependency already exists
        if "javax.annotation:javax.annotation-api" not in content:
            dependency_line = "dependencies {\n    implementation 'javax.annotation:javax.annotation-api:1.3.2'"
            content = content.replace("dependencies {", dependency_line)
            
            with open(gradle_build_file, "w") as file:
                file.write(content)
    
    # Build project
    print_step("Building java-tron (this may take some time)...")
    result = run_command("./gradlew clean build -x test", check=False)
    
    # Check build success
    if not os.path.exists(f"{TRON_DIR}/build/libs/FullNode.jar"):
        print_error("java-tron build failed. Check build logs.")
        sys.exit(1)
    
    print_success("java-tron built successfully")

def create_config_files():
    """Create configuration files."""
    print_step("Creating configuration files...")
    
    # Configuration file content
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
    
    # Startup script content
    start_script_content = """#!/bin/bash
java -Xmx24g -XX:+UseConcMarkSweepGC -jar /home/java-tron/build/libs/FullNode.jar -c /home/java-tron/last-conf.conf -d /home/java-tron/output-directory/
"""
    
    # Write startup script
    with open(START_SCRIPT, "w") as f:
        f.write(start_script_content)
    
    # Set execute permissions
    os.chmod(START_SCRIPT, os.stat(START_SCRIPT).st_mode | stat.S_IEXEC)
    
    # systemd service content
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
    
    # Create README.md
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
"""
    
    # Write README.md
    with open(f"{TRON_DIR}/README.md", "w") as f:
        f.write(readme_content)
    
    print_success("Configuration files created")

def setup_systemd():
    """Configure autostart via systemd."""
    print_step("Setting up autostart via systemd...")
    
    # Reload systemd to detect new service
    run_command("systemctl daemon-reload")
    
    # Enable autostart
    run_command("systemctl enable tron-node")
    
    print_success("Autostart configured")

def start_node():
    """Start the node."""
    print_step("Starting TRON node...")
    
    # Start service
    run_command("systemctl start tron-node")
    
    # Check status
    time.sleep(5)  # Give time to start
    status = run_command("systemctl is-active tron-node", check=False)
    
    if status == "active":
        print_success("TRON node successfully started!")
    else:
        print_warning("TRON node is starting, check status in a few minutes with 'systemctl status tron-node'")

def main():
    """Main function of the script."""
    print(f"{GREEN}===========================================")
    print(f"   TRON Lite Full Node Installation   ")
    print(f"==========================================={RESET}")
    
    # Check root privileges
    check_root()
    
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
    
    print(f"\n{GREEN}===========================================")
    print(f"   TRON Lite Full Node successfully installed!   ")
    print(f"==========================================={RESET}")
    print(f"\nDocumentation can be found in: {TRON_DIR}/README.md")
    print(f"To check node status run: systemctl status tron-node")
    print(f"To view logs run: journalctl -u tron-node -f")

if __name__ == "__main__":
    main()
