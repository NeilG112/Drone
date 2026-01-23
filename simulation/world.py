import numpy as np
import random

class GridMap:
    def __init__(self, width, height, map_type='floorplan', complexity=0.67, room_size=15, num_rooms=10, num_targets=1, seed=None):
        self.width = width
        self.height = height
        self.map_type = map_type
        self.complexity = complexity 
        self.room_size = room_size # Control Room Size (side length)
        self.num_rooms = num_rooms # Target number of rooms
        self.num_targets = num_targets # Number of targets to place
        self.seed = seed
        self.rng = random.Random(seed)
        
        # 0 = free, 1 = obstacle
        self.grid = np.zeros((height, width), dtype=int)
        
        # Targets
        self.targets = []
        
        # Start Position
        self.start_pos = (0, 0)
        
        # Cache for optimization
        self._free_cells = None
        
        self.generate_map()
        
    def generate_map(self):
        """Generates map (floorplan only)."""
        self._generate_floorplan()

    def _generate_floorplan(self):
        """Generates rooms connected by corridors with block obstacles."""
        # 1. Fill with walls first
        self.grid.fill(1)
        
        rooms = []
        
        # Room dimensions based on Literal room_size (side length)
        # room_size 5 => ~5x5 rooms
        target_dim = max(3, self.room_size)
        min_dim = max(3, target_dim - 1)
        max_dim = target_dim + 2
        
        total_attempts = 0
        max_attempts = 10000 # Try very hard to fit all rooms
        
        # 2. Place random rooms until we match target count
        while len(rooms) < self.num_rooms and total_attempts < max_attempts:
            total_attempts += 1
            
            w = self.rng.randint(min_dim, max_dim)
            h = self.rng.randint(min_dim, max_dim)
            
            if w >= self.width or h >= self.height: continue
            
            x = self.rng.randint(1, self.width - w - 1)
            y = self.rng.randint(1, self.height - h - 1)
            
            # Check overlap logic (with 1 cell buffer for walls)
            new_room = {'x': x, 'y': y, 'w': w, 'h': h}
            
            overlap = False
            for r in rooms:
                # Strictly separate rooms by 1 wall
                if (x < r['x'] + r['w'] + 1 and x + w + 1 > r['x'] and
                    y < r['y'] + r['h'] + 1 and y + h + 1 > r['y']):
                    overlap = True
                    break
            
            if not overlap:
                rooms.append(new_room)
                # Carve room (vectorized)
                self.grid[y:y+h, x:x+w] = 0
                        
        # 3. Connect rooms with nearest-neighbor approach
        if len(rooms) > 1:
            # Connect each room to its 2-3 nearest neighbors
            for i, room in enumerate(rooms):
                neighbors = self._find_nearest_neighbors(room, rooms, exclude_idx=i, count=min(3, len(rooms)-1))
                for neighbor in neighbors[:2]:  # Connect to 2 nearest
                    self._connect_rooms(room, neighbor)

        # 4. Add Block Clutter
        self._add_object_clutter(rooms)
            
        self._post_process()

    def _find_nearest_neighbors(self, room, all_rooms, exclude_idx, count):
        """Find nearest neighbor rooms by center distance."""
        cx = room['x'] + room['w'] // 2
        cy = room['y'] + room['h'] // 2
        
        distances = []
        for i, other in enumerate(all_rooms):
            if i == exclude_idx:
                continue
            ox = other['x'] + other['w'] // 2
            oy = other['y'] + other['h'] // 2
            dist = abs(cx - ox) + abs(cy - oy)  # Manhattan distance
            distances.append((dist, other))
        
        distances.sort(key=lambda x: x[0])
        return [room for _, room in distances[:count]]

    def _connect_rooms(self, r1, r2):
        """Connect two rooms with a corridor that breaks up long segments."""
        cx1, cy1 = r1['x'] + r1['w'] // 2, r1['y'] + r1['h'] // 2
        cx2, cy2 = r2['x'] + r2['w'] // 2, r2['y'] + r2['h'] // 2
        
        dx = abs(cx2 - cx1)
        dy = abs(cy2 - cy1)
        
        # For long distances, add intermediate waypoints
        if dx > 10 or dy > 10:
            # Add 1-2 intermediate waypoints for zigzag
            num_waypoints = 1 if max(dx, dy) < 20 else 2
            waypoints = [(cx1, cy1)]
            
            for i in range(num_waypoints):
                # Interpolate with some randomness
                t = (i + 1) / (num_waypoints + 1)
                wx = int(cx1 + (cx2 - cx1) * t + self.rng.randint(-3, 3))
                wy = int(cy1 + (cy2 - cy1) * t + self.rng.randint(-3, 3))
                # Clamp to bounds
                wx = max(1, min(self.width - 2, wx))
                wy = max(1, min(self.height - 2, wy))
                waypoints.append((wx, wy))
            
            waypoints.append((cx2, cy2))
            
            # Connect consecutive waypoints
            for i in range(len(waypoints) - 1):
                self._carve_corridor(waypoints[i][0], waypoints[i][1], 
                                   waypoints[i+1][0], waypoints[i+1][1])
        else:
            # Short distance, simple L-shaped corridor
            self._carve_corridor(cx1, cy1, cx2, cy2)
    
    def _carve_corridor(self, x1, y1, x2, y2):
        """Carve an L-shaped corridor between two points (optimized)."""
        # Clamp coordinates to valid bounds
        x1 = max(0, min(x1, self.width - 1))
        x2 = max(0, min(x2, self.width - 1))
        y1 = max(0, min(y1, self.height - 1))
        y2 = max(0, min(y2, self.height - 1))
        
        # Randomly choose H-then-V or V-then-H
        if self.rng.choice([True, False]):
            # Horizontal then Vertical (vectorized)
            x_start, x_end = min(x1, x2), max(x1, x2)
            self.grid[y1, x_start:x_end+1] = 0
            y_start, y_end = min(y1, y2), max(y1, y2)
            self.grid[y_start:y_end+1, x2] = 0
        else:
            # Vertical then Horizontal (vectorized)
            y_start, y_end = min(y1, y2), max(y1, y2)
            self.grid[y_start:y_end+1, x1] = 0
            x_start, x_end = min(x1, x2), max(x1, x2)
            self.grid[y2, x_start:x_end+1] = 0

    def _add_object_clutter(self, rooms):
        # Complexity controls density of objects
        # 0.0 -> 0 objects
        # 1.0 -> High density objects
        
        if self.complexity <= 0.05: return

        for r in rooms:
            # Number of objects per room based on size and complexity
            room_area = r['w'] * r['h']
            # E.g. 10% to 30% coverage
            target_obj_area = room_area * (self.complexity * 0.3)
            current_obj_area = 0
            
            attempts = 0
            while current_obj_area < target_obj_area and attempts < 20:
                attempts += 1
                # Object size 1x1 to 3x3 depending on room size
                max_obj = min(3, min(r['w'], r['h']) - 2)
                if max_obj < 1: max_obj = 1
                
                ow = self.rng.randint(1, max_obj)
                oh = self.rng.randint(1, max_obj)
                
                ox = self.rng.randint(r['x'] + 1, r['x'] + r['w'] - ow - 1)
                oy = self.rng.randint(r['y'] + 1, r['y'] + r['h'] - oh - 1)
                
                # Place object
                # Don't overwrite if it chunks too much? No, just place it.
                # Actually, check if we are blocking the ONLY path? Hard to know.
                # Just place it. Walls are 1.
                self.grid[oy:oy+oh, ox:ox+ow] = 1
                current_obj_area += (ow * oh)

    def _post_process(self):
        """Ensure start is free and place multiple targets (optimized)."""
        # Pre-compute and cache free cells (much faster than argwhere)
        free_y, free_x = np.where(self.grid == 0)
        self._free_cells = list(zip(free_x, free_y))  # Store as (x, y) tuples
        
        if len(self._free_cells) > 0:
            # Randomly select start position from free cells
            self.start_pos = self.rng.choice(self._free_cells)
            
            # Place multiple targets (exclude start position)
            target_candidates = [cell for cell in self._free_cells if cell != self.start_pos]
            
            # Determine how many targets we can actually place
            num_to_place = min(self.num_targets, len(target_candidates))
            
            if num_to_place > 0:
                # Randomly sample without replacement
                selected_targets = self.rng.sample(target_candidates, num_to_place)
                self.targets.extend(selected_targets)
            elif len(self._free_cells) == 1:
                # Fallback: only one free cell exists, use start as target
                self.targets.append(self.start_pos)
        else:
            # Fallback if map is completely full (shouldn't happen)
            self.start_pos = (0, 0)
            self.grid[0, 0] = 0
            self.targets.append((self.width-1, self.height-1))
            self.grid[self.height-1, self.width-1] = 0
            self._free_cells = [self.start_pos, self.targets[0]]

    def is_obstacle(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y, x] == 1
        return True # Treat out of bounds as obstacle to prevent leaving map

    def to_dict(self):
        return {
            'width': int(self.width),
            'height': int(self.height),
            'grid': self.grid.tolist(),  # Convert NumPy array to list
            'targets': [(int(x), int(y)) for x, y in self.targets],  # Convert tuples with ints
            'start_pos': (int(self.start_pos[0]), int(self.start_pos[1]))  # Convert tuple with ints
        }

    def move_target(self, target_idx, dx, dy):
        """Moves a specific target by dx, dy if valid and free."""
        if 0 <= target_idx < len(self.targets):
            tx, ty = self.targets[target_idx]
            nx, ny = tx + dx, ty + dy
            
            # Check bounds
            if 0 <= nx < self.width and 0 <= ny < self.height:
                # Check collision (must be free space)
                # Ideally targets don't move into walls.
                if self.grid[ny, nx] == 0:
                    # Also check if it overlaps with other targets? 
                    # Usually okay, but let's avoid it for clarity?
                    if (nx, ny) not in self.targets:
                         self.targets[target_idx] = (nx, ny)
                         return True
        return False
