import numpy as np

class Simulation:
    def __init__(self, world, policy, max_steps=500):
        self.world = world
        self.policy = policy
        self.max_steps = max_steps
        # Create agent at (0,0)
        from simulation.agent import Agent
        self.agent = Agent(world.start_pos[0], world.start_pos[1], world.width, world.height)
        
    def run(self):
        history = []
        
        # Initial belief state for diffing
        prev_belief = np.full((self.world.height, self.world.width), -1, dtype=int)
        
        # Initial sense
        self.agent.sense(self.world)
        
        # Record Initial State (Compressed)
        curr_belief = self.agent.belief_map
        rows, cols = np.where(curr_belief != prev_belief)
        diff = [[int(r), int(c), int(curr_belief[r, c])] for r, c in zip(rows, cols)]
        prev_belief = curr_belief.copy()
        
        state = {
            'x': int(self.agent.x),
            'y': int(self.agent.y),
            'belief_diff': diff,
            'found_targets': [(int(x), int(y)) for x, y in self.agent.found_targets],
            'step': 0
        }
        history.append(state)
        
        steps = 0
        success = False
        
        # New Metrics
        collisions = 0
        turns = 0
        last_dx, last_dy = 0, 0
        
        while steps < self.max_steps:
            # Check completion (found all targets)
            if len(self.agent.found_targets) == len(self.world.targets):
                success = True
                break
                
            # Decision
            dx, dy = self.policy.select_action(self.agent)
            
            # Track Turns
            if (dx != last_dx or dy != last_dy) and steps > 0:
                turns += 1
            last_dx, last_dy = dx, dy
            
            # Act
            moved = self.agent.move(dx, dy, self.world)
            if not moved and (dx != 0 or dy != 0):
                # Bumped into wall or boundary
                collisions += 1
                
            # Sense
            self.agent.sense(self.world)
            
            # Record (Compressed)
            curr_belief = self.agent.belief_map
            rows, cols = np.where(curr_belief != prev_belief)
            diff = [[int(r), int(c), int(curr_belief[r, c])] for r, c in zip(rows, cols)]
            prev_belief = curr_belief.copy()
            
            state = {
                'x': int(self.agent.x),
                'y': int(self.agent.y),
                'belief_diff': diff,
                'found_targets': [(int(x), int(y)) for x, y in self.agent.found_targets],
                'step': steps + 1
            }
            history.append(state)
            
            steps += 1
            
        # extensive metrics calculation
        total_cells = self.world.width * self.world.height
        
        # Coverage: cells in belief map that are NOT -1 (unknown) - OPTIMIZED
        belief = self.agent.belief_map
        known_cells = np.count_nonzero(belief != -1)
        coverage_percent = (known_cells / total_cells) * 100
        
        # Obstacle Density (Ground Truth)
        obstacles = np.count_nonzero(self.world.grid == 1)
        obstacle_density = (obstacles / total_cells) * 100
        
        # Unique cells visited (path length redundancy check)
        unique_visited = len(set([(s['x'], s['y']) for s in history]))
        
        # Search Efficiency: Unique Visited / Total Steps (Higher is better, max 1.0)
        efficiency = (unique_visited / steps) if steps > 0 else 0
            
        return {
            'stats': {
                'success': success,
                'steps': steps,
                'targets_total': len(self.world.targets),
                'targets_found': len(self.agent.found_targets),
                'coverage_percent': round(coverage_percent, 2),
                'obstacle_density': round(obstacle_density, 2),
                'unique_visited': unique_visited,
                'efficiency': round(efficiency, 3),
                'turns': turns,
                'collisions': collisions,
                'map_width': self.world.width,
                'map_height': self.world.height
            },
            'history': history,
            'config': {
                'width': self.world.width,
                'height': self.world.height,
                'policy': self.policy.__class__.__name__,
                'seed': self.world.seed
            }
        }

