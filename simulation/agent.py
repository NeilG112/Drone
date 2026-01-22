import numpy as np

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
        
        # Use shared found targets list if provided (multi-drone coordination)
        if shared_found_targets is not None:
            self.found_targets = shared_found_targets
        else:
            self.found_targets = []
            
        self.path = [(start_x, start_y)]

    def move(self, dx, dy, world):
        new_x, new_y = self.x + dx, self.y + dy
        
        # Check boundary and collision (against ground truth world)
        if 0 <= new_x < self.width and 0 <= new_y < self.height:
            if not world.is_obstacle(new_x, new_y):
                self.x = new_x
                self.y = new_y
                self.path.append((self.x, self.y))
                return True
        return False

    def sense(self, world):
        """Simulates range sensor with line-of-sight (blocked by walls)."""
        sensor_range = 3
        
        for dy in range(-sensor_range, sensor_range + 1):
            for dx in range(-sensor_range, sensor_range + 1):
                nx, ny = self.x + dx, self.y + dy
                
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    # Check if we have line of sight to this cell
                    if self._has_line_of_sight(self.x, self.y, nx, ny, world):
                        # Update belief map with Ground Truth
                        if world.is_obstacle(nx, ny):
                            self.belief_map[ny, nx] = 1
                        else:
                            self.belief_map[ny, nx] = 0
                            
                        # Check for targets
                        if (nx, ny) in world.targets:
                            if (nx, ny) not in self.found_targets:
                                self.found_targets.append((nx, ny))
    
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
            'found_targets': [(int(x), int(y)) for x, y in self.found_targets]
        }
