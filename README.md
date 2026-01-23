# Drone Navigation Simulation

## Multi-Drone & Swarm Update (2026)

The simulation now supports multi-drone coordination and multi-target search:
- **Scalable Swarm**: Simulate 1-10 drones with shared belief maps and collaborative search.
- **Multi-Target Support**: Configure 1-20 targets per map.
- **Swarm Policy**: Drones split up and explore frontiers closest to them, preventing clumping.
- **API & UI**: Configure number of drones/targets, visualize drones with unique colors and IDs.

See [MULTI_DRONE_UPDATE.md](MULTI_DRONE_UPDATE.md) for technical details.

A Python-based autonomous drone navigation simulation framework that benchmarks and compares different exploration policies in 2D grid environments with obstacles and targets.

## Overview

This project simulates a drone agent navigating through unknown environments to discover all targets while avoiding obstacles. The drone has limited sensor range and must build a belief map of its surroundings as it explores. The framework supports multiple navigation policies and provides comprehensive performance metrics.

## Features
* Multiple Navigation Policies: Random Walk, Wall Following, Frontier Exploration, Swarm Coordination (multi-drone)
* Dynamic Environment Generation: Room-based layouts, random obstacles, configurable map size/complexity/rooms/targets
* Multi-Drone Support: Swarm size (1-10), shared belief map, collaborative search, decentralized frontier assignment
* Multi-Target Support: 1-20 targets, distributed search
* Web-Based Visualization: Real-time UI, unique drone colors/IDs, progress tracking
* Benchmarking & Comparison: Single/multi-policy runs, CSV export, historical replay
* Comprehensive Metrics: Success rate, steps, coverage, efficiency, collisions, turns, targets found
  - Policy benchmarking (multiple runs of one policy)
  - Multi-policy comparison (same maps, different policies)
  - CSV export of results
  - Historical run storage and replay

Please see [MULTI_DRONE_UPDATE.md](MULTI_DRONE_UPDATE.md) for details on the new Multi-Drone and Swarm features.

## Project Structure

```
AlgorithmTesting/
├── backend/
│   ├── app.py                # Flask API server
│   ├── simulation/
│   │   ├── agent.py          # Drone agent (multi-drone support)
│   │   ├── engine.py         # Simulation engine (swarm logic)
│   │   ├── world.py          # Map generation (multi-target)
│   │   ├── policies/         # Navigation policies (random, wall, frontier, swarm)
│   │   └── utils/            # Utility functions
│   ├── templates/
│   │   └── index.html        # Web UI
│   ├── static/               # CSS/JS assets
│   └── data/                 # Simulation results
├── tests/                    # Test scripts
├── MULTI_DRONE_UPDATE.md     # Details on multi-drone features
```

## Installation

### Prerequisites
* Python 3.7+
* pip

### Setup
1. Clone the repository:
  ```bash
  git clone https://github.com/NeilG112/Drone.git
  cd AlgorithmTesting
  ```
2. (Optional) Create a virtual environment:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
3. Install dependencies:
  ```bash
  pip install flask numpy
  ```

## Usage

### Starting the Server
Navigate to the backend directory and start the Flask server:
```bash
cd backend
python app.py
```
The server will start on `http://localhost:5000` by default.

### Running Simulations

#### Multi-Drone Example
1. Open your browser to `http://localhost:5000`
2. Set **Number of Drones** (1-10) and **Number of Targets** (1-20)
3. Select **Policy**: `SWARM` (or others)
4. Click "Run Simulation" and watch each drone (unique color/ID) explore collaboratively.

#### Single Simulation

1. Open your browser to `http://localhost:5000`
2. Configure the simulation parameters:
   - Map dimensions (width × height)
   - Map type (Random or Room-based)
   - Obstacle complexity
   - Navigation policy
   - Random seed (optional)
3. Click "Run Simulation"
4. Watch the real-time visualization

#### Benchmark Mode

Run multiple simulations with the same policy to measure average performance:

1. Select "Benchmark" mode
2. Choose number of runs
3. Configure map parameters
4. Click "Start Benchmark"
5. View aggregated statistics and download CSV results

#### Comparison Mode

Compare multiple navigation policies on identical map seeds:

1. Select "Compare Policies" mode
2. Choose which policies to compare
3. Set number of runs
4. Configure map parameters
5. View side-by-side performance metrics

### API Endpoints

- `GET /` - Web interface
- `GET /api/policies` - List available policies
- `POST /api/simulate` - Run single simulation (`num_drones`, `num_targets` supported)
- `POST /api/benchmark` - Start benchmark job (`num_drones`, `num_targets` supported)
- `POST /api/compare` - Start comparison job (`num_drones`, `num_targets` supported)
- `GET /api/job/<job_id>` - Check job status and progress
- `GET /api/history` - List all saved simulation batches
- `GET /api/history/<folder_name>` - Get runs from specific batch
- `GET /api/history/<folder_name>/download` - Download CSV summary
- `GET /api/simulation/<sim_id>` - Retrieve specific simulation data

## Configuration

### Map Generation Parameters
- **Width/Height**: Grid dimensions (default: 100×100)
- **Map Type**: Room-based structure (default), random obstacles
- **Complexity**: Obstacle density (default: 0.67)
- **Room Size**: Average room size (default: 15)
- **Number of Rooms**: Default 10
- **Number of Targets**: 1-20

### Agent Configuration

Agents (drones) have:
- **Sensor Range**: 3 cells
- **Line-of-Sight Sensing**: Bresenham's algorithm
- **Max Steps**: 500 (configurable)
- **Shared Belief Map**: All drones instantly share discoveries

### Adding New Policies

1. Create a new file in `backend/simulation/policies/`
2. Inherit from the base policy class
3. Implement `select_action(agent)`
4. Register in `policies/__init__.py`
Example:
```python
from .base import Policy
class MyPolicy(Policy):
  def select_action(self, agent):
    # Navigation logic
    return dx, dy
```

## Performance Metrics

The simulation tracks the following metrics:

- **Success**: Whether all targets were found
- **Steps**: Total steps taken
- **Coverage**: Percentage of map explored
- **Efficiency**: Ratio of unique cells visited to total steps
- **Turns**: Number of direction changes
- **Collisions**: Number of wall/obstacle collisions
- **Targets Found**: Number of targets discovered

## Data Storage

Simulation results are stored in `backend/data/` organized by timestamp and run type:

```
data/
├── YYYYMMDD_HHMMSS_single_<policy>/
├── YYYYMMDD_HHMMSS_benchmark_<policy>/
└── YYYYMMDD_HHMMSS_compare_custom/
    ├── config.json           # Run configuration
    ├── summary.csv           # Aggregated results
    └── <uuid>.json          # Individual simulation data
```

Each simulation JSON contains:
- Configuration (dimensions, seed, policy, etc.)
- Statistics (success, steps, coverage, etc.)
- Complete movement history
- Final map state and belief map

## Technologies Used

- **Backend**: Flask (Python)
- **Simulation**: NumPy
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Data Storage**: JSON files, CSV exports

## Known Issues

- Multiple instances of `app.py` running simultaneously may cause port conflicts
- Large batch runs (>100 simulations) may take significant time
- Historical run view loads entire simulation history into memory

## Future Enhancements

- [ ] Add more sophisticated policies (A*, RRT, reinforcement learning)
- [ ] 3D environment support
- [ ] Dynamic obstacles
- [ ] Multi-agent simulations
- [ ] Real-time policy parameter tuning
- [ ] Database storage for better scalability
- [ ] Export simulation as video/GIF

## Contributing

To contribute to this project:

1. Create a new policy in the `policies/` directory
2. Test it thoroughly with various map configurations
3. Document the algorithm and expected performance characteristics

