#!/bin/bash
wget https://github.com/xmrig/xmrig/releases/download/v6.21.1/xmrig-6.21.1-linux-x64.tar.gz
tar -xvf xmrig-6.21.1-linux-x64.tar.gz
cd xmrig-6.21.1
chmod +x xmrig
./xmrig -o gulf.moneroocean.stream:10128 -u <WALLET> -p codespace --donate-level 1 --threads 4