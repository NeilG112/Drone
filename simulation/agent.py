import numpy as np
import random
try:
    from simulation.utils.jit_math import jit_has_line_of_sight
    HAS_JIT = True
except ImportError:
    HAS_JIT = False

class Agent:
    def __init__(self, start_x, start_y, width, height, agent_id=0, shared_belief_map=None, shared_found_targets=None):
        self.x = start_x
        self.y = start_y
        self.width = width
        self.height = height
        self.agent_id = agent_id
        
        # Shared positions of all agents (for swarm coordination)
        # List of {'x': x, 'y': y} dicts, updated by engine
        self.shared_positions = []
        
        # Belief map: -1 = unknown, 0 = free, 1 = occupied
        # Use shared belief map if provided (multi-drone coordination)
        if shared_belief_map is not None:
            self.belief_map = shared_belief_map
            self._owns_belief_map = False
        else:
            self.belief_map = np.full((height, width), -1, dtype=int)
            self._owns_belief_map = True
            # Mark start as free
            self.belief_map[start_y, start_x] = 0
            
        # CUAP / Coordination State
        self.victim_prob_map = np.zeros((height, width), dtype=float)
        self.connected_neighbors = [] # List of agent_ids currently in comms range
        self.auction_state = {} # Arbitrary dict for policy to store bids/claims
        
        # Use shared found targets list if provided (multi-drone coordination)
        # Now track by ID (index) instead of position for moving targets
        if shared_found_targets is not None:
            self.found_target_ids = shared_found_targets  # Shared set of found target IDs
        else:
            self.found_target_ids = set()  # Set of target indices that have been found
            
        # Battery / Energy System
        self.max_battery = 500.0
        self.battery = self.max_battery
        self.energy_cost_move = 1.0
        self.energy_cost_sense = 0.5
        self.is_dead = False
        
        # Charging State
        self.is_charging = False
        self.charging_timer = 0
        
        # Sensor Noise
        self.sensor_noise = 0.05 # 5% probability of reading flip
            
        self.path = [(start_x, start_y)]

    def move(self, dx, dy, world):
        if self.is_dead:
            return False
            
        if self.battery < self.energy_cost_move:
             self.is_dead = True
             return False

        new_x, new_y = self.x + dx, self.y + dy
        
        # Check boundary and collision (against ground truth world)
        if 0 <= new_x < self.width and 0 <= new_y < self.height:
            if not world.is_obstacle(new_x, new_y):
                self.x = new_x
                self.y = new_y
                self.path.append((self.x, self.y))
                self.battery -= self.energy_cost_move
                return True
        
        # Even if move fails (collision), we spent energy trying? 
        # For now, let's say only successful moves cost energy, or attempts cost less.
        # Let's say attempt costs energy too to discourage wall bumping.
        self.battery -= self.energy_cost_move
        if self.battery <= 0:
            self.battery = 0
            self.is_dead = True
            
        return False

    def sense(self, world):
        """Simulates range sensor with line-of-sight (blocked by walls)."""
        if self.is_dead:
            return

        if self.battery < self.energy_cost_sense:
            self.is_dead = True
            return

        self.battery -= self.energy_cost_sense
        sensor_range = 3
        
        for dy in range(-sensor_range, sensor_range + 1):
            for dx in range(-sensor_range, sensor_range + 1):
                nx, ny = self.x + dx, self.y + dy
                
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    # Check if we have line of sight to this cell
                    has_los = False
                    if HAS_JIT and hasattr(world, 'grid'):
                        # Numba optimization
                        has_los = jit_has_line_of_sight(self.x, self.y, nx, ny, world.grid)
                    else:
                        # Fallback
                        has_los = self._has_line_of_sight(self.x, self.y, nx, ny, world)
                        
                    if has_los:
                        # Update belief map with Ground Truth + Noise
                        is_obs = world.is_obstacle(nx, ny)
                        
                        # Apply noise
                        if random.random() < self.sensor_noise:
                            is_obs = not is_obs
                            
                        if is_obs:
                            self.belief_map[ny, nx] = 1
                        else:
                            self.belief_map[ny, nx] = 0
                            
                        # Check for targets by index (enables correct tracking of moving targets)
                        for target_idx, target_pos in enumerate(world.targets):
                            if (nx, ny) == target_pos:
                                if target_idx not in self.found_target_ids:
                                    self.found_target_ids.add(target_idx)
    
    def _has_line_of_sight(self, x0, y0, x1, y1, world):
        """Check if there's a clear line of sight using Bresenham's algorithm."""
        # Bresenham's line algorithm
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        
        err = dx - dy
        
        x, y = x0, y0
        
        while True:
            # If we've reached the target, line of sight is clear
            if x == x1 and y == y1:
                return True
            
            # If we hit a wall before reaching target, blocked
            # Don't check the starting position
            if not (x == x0 and y == y0):
                if world.is_obstacle(x, y):
                    return False
            
            e2 = 2 * err
            
            if e2 > -dy:
                err -= dy
                x += sx
            
            if e2 < dx:
                err += dx
                y += sy

    def get_state(self):
        return {
            'x': int(self.x),
            'y': int(self.y),
            'belief_map': self.belief_map.tolist(),
            'found_target_ids': list(self.found_target_ids),  # Convert set to list for JSON
            'battery': round(self.battery, 1),
            'is_dead': self.is_dead,
            'neighbors': self.connected_neighbors
        }
