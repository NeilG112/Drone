# Drone Navigation Simulation

A Python-based autonomous drone navigation simulation framework that benchmarks and compares different exploration policies in 2D grid environments with obstacles and targets.

## Overview

This project simulates a drone agent navigating through unknown environments to discover all targets while avoiding obstacles. The drone has limited sensor range and must build a belief map of its surroundings as it explores. The framework supports multiple navigation policies and provides comprehensive performance metrics.

## Features

- **Multiple Navigation Policies**:
  - Random Walk: Random exploration
  - Wall Following: Systematic wall-hugging navigation
  - Frontier Exploration: Advanced frontier-based path planning
  
- **Dynamic Environment Generation**:
  - Random obstacle placement
  - Room-based structured layouts
  - Configurable map dimensions, complexity, room size, and number of rooms

- **Comprehensive Metrics**:
  - Success rate and completion steps
  - Map coverage percentage
  - Search efficiency (unique cells vs. total steps)
  - Collision count and turn count
  - Target discovery rate

- **Web-Based Visualization**:
  - Interactive UI for running simulations
  - Real-time visualization of drone movement
  - Heatmap visualization of explored areas
  - Progress tracking for batch runs

- **Benchmarking & Comparison**:
  - Single simulation runs
  - Policy benchmarking (multiple runs of one policy)
  - Multi-policy comparison (same maps, different policies)
  - CSV export of results
  - Historical run storage and replay

## Project Structure

```
DroneNavigation/
├── backend/
│   ├── app.py                      # Flask API server
│   ├── simulation/
│   │   ├── agent.py               # Drone agent with sensing and movement
│   │   ├── engine.py              # Simulation engine and metrics
│   │   ├── world.py               # Grid map generation and management
│   │   └── policies/              # Navigation policy implementations
│   │       ├── base.py
│   │       ├── random_walk.py
│   │       ├── wall_follow.py
│   │       └── frontier.py
│   ├── templates/
│   │   └── index.html             # Web UI
│   ├── static/                    # Static assets
│   └── data/                      # Simulation results storage
```

## Installation

### Prerequisites

- Python 3.7+
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/NeilG112/Drone.git
cd DroneNavigation
```

2. Install dependencies:
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
- `POST /api/simulate` - Run single simulation
- `POST /api/benchmark` - Start benchmark job
- `POST /api/compare` - Start comparison job
- `GET /api/job/<job_id>` - Check job status and progress
- `GET /api/history` - List all saved simulation batches
- `GET /api/history/<folder_name>` - Get runs from specific batch
- `GET /api/history/<folder_name>/download` - Download CSV summary
- `GET /api/simulation/<sim_id>` - Retrieve specific simulation data

## Configuration

### Map Generation Parameters

- **Width/Height**: Grid dimensions (default: 20×20)
- **Map Type**: 
  - `random`: Random obstacle placement
  - `rooms`: Room-based structure with corridors
- **Complexity**: Obstacle density (0.0-1.0, default: 0.2)
- **Room Size**: Average room dimensions for room-based maps
- **Number of Rooms**: Target room count (may vary based on constraints)

### Agent Configuration

The agent has the following characteristics (configurable in `agent.py`):

- **Sensor Range**: 3 cells in all directions
- **Line-of-Sight Sensing**: Uses Bresenham's algorithm
- **Max Steps**: 500 steps per simulation (configurable in `engine.py`)

### Adding New Policies

1. Create a new file in `backend/simulation/policies/`
2. Inherit from the base policy class
3. Implement the `select_action(agent)` method
4. Register the policy in `policies/__init__.py`

Example:

```python
from .base import Policy

class MyPolicy(Policy):
    def select_action(self, agent):
        # Your navigation logic here
        # Return (dx, dy) where dx, dy ∈ {-1, 0, 1}
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


