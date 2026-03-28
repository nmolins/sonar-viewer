# Sonar Viewer

A lightweight web dashboard for [sonar](https://github.com/raskrebs/sonar), the Docker port scanner.

Visualize all open ports and running containers on your homelab server with a clean, dark-themed interface.

![Python](https://img.shields.io/badge/python-3.7+-blue) ![Dependencies](https://img.shields.io/badge/dependencies-none-green)

## Features

- **Live dashboard** — view all ports, containers, and processes at a glance
- **Refresh** — re-scan ports with a single click (calls `sonar list --stats --json`)
- **Search** — filter by name, image, or port number
- **Filter** — toggle between Docker / Host / System services
- **Sort** — by name, port, CPU, or RAM usage
- **Next available ports** — find free ports instantly (calls `sonar next`)
- **Auto-categorization** — containers are grouped by type (Media, Arr, Infra, Network, Security, etc.)
- **Zero dependencies** — Python stdlib only, no `pip install` needed

## Quick start

```bash
git clone git@github.com:nmolins/sonar-viewer.git
cd sonar-viewer
python3 server.py
```

Open `http://your-server:7680` in your browser.

## Options

```bash
python3 server.py --port 8080       # custom port
python3 server.py --bind 127.0.0.1  # bind to localhost only
SONAR_CMD=./sonar python3 server.py # custom sonar binary path
```

## Requirements

- Python 3.7+
- [sonar](https://github.com/raskrebs/sonar) installed on the same machine
