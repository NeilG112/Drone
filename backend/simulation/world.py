import numpy as np
import random

class GridMap:
    def __init__(self, width, height, seed=None):
        self.width = width
        self.height = height
        self.seed = seed
        self.rng = random.Random(seed)
        
        # 0 = free, 1 = obstacle
        self.grid = np.zeros((height, width), dtype=int)
        
        # Targets
        self.targets = []
        
        self.generate_map()
        
    def generate_map(self):
        """Generates a random map with walls and targets."""
        # Simple random walls for now
        num_obstacles = int(self.width * self.height * 0.2) # 20% obstacles
        
        for _ in range(num_obstacles):
            x = self.rng.randint(0, self.width - 1)
            y = self.rng.randint(0, self.height - 1)
            self.grid[y, x] = 1
            
        # Ensure start position (0,0) is free
        self.grid[0, 0] = 0
        
        # Add a target
        while True:
            tx = self.rng.randint(0, self.width - 1)
            ty = self.rng.randint(0, self.height - 1)
            if self.grid[ty, tx] == 0 and (tx != 0 or ty != 0):
                self.targets.append((tx, ty))
                break

    def is_obstacle(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y, x] == 1
        return True # Treat out of bounds as obstacle to prevent leaving map

    def to_dict(self):
        return {
            'width': self.width,
            'height': self.height,
            'grid': self.grid.tolist(),
            'targets': self.targets
        }
