import numpy as np

# Try to import Numba, if checks fail, fallback to Python/NumPy
HAS_JIT = False
try:
    from numba import jit
    HAS_JIT = True
except (ImportError, AttributeError):
    # AttributeError handling for the coverage conflict
    def jit(nopython=True):
        def decorator(func):
            return func
        return decorator

if HAS_JIT:
    @jit(nopython=True)
    def jit_has_line_of_sight(x0, y0, x1, y1, grid):
        """
        Bresenham's Line Algorithm optimized with Numba.
        grid: 2D numpy array (1=obstacle, 0=free)
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        
        err = dx - dy
        
        x, y = x0, y0
        
        while True:
            if x == x1 and y == y1:
                return True
                
            if not (x == x0 and y == y0):
                if grid[y, x] == 1:
                    return False
                    
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    @jit(nopython=True)
    def jit_compute_voronoi(owners, shared_positions, rows, cols):
        """
        Multi-Source BFS for Voronoi logic (Numba).
        """
        queue_r = np.zeros(rows * cols, dtype=np.int32)
        queue_c = np.zeros(rows * cols, dtype=np.int32)
        queue_id = np.zeros(rows * cols, dtype=np.int32)
        
        head = 0
        tail = 0
        
        # Init sources
        for i in range(len(shared_positions)):
            c = shared_positions[i, 0]
            r = shared_positions[i, 1]
            
            if c >= 0 and c < cols and r >= 0 and r < rows:
                owners[r, c] = i
                queue_r[tail] = r
                queue_c[tail] = c
                queue_id[tail] = i
                tail += 1
                
        while head < tail:
            r = queue_r[head]
            c = queue_c[head]
            owner = queue_id[head]
            head += 1
            
            # Neighbors
            dr = [-1, 1, 0, 0]
            dc = [0, 0, -1, 1]
            
            for k in range(4):
                nr = r + dr[k]
                nc = c + dc[k]
                
                if 0 <= nr < rows and 0 <= nc < cols:
                    if owners[nr, nc] == -1:
                        owners[nr, nc] = owner
                        queue_r[tail] = nr
                        queue_c[tail] = nc
                        queue_id[tail] = owner
                        tail += 1
        
        return owners

else:
    # FALLBACK IMPLEMENTATIONS (Pure Python or NumPy)
    
    def jit_has_line_of_sight(x0, y0, x1, y1, grid):
        """Pure Python Bresenham (Slow)"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            if x == x1 and y == y1: return True
            if not (x==x0 and y==y0):
                if grid[y, x] == 1: return False
            e2 = 2 * err
            if e2 > -dy: err -= dy; x += sx
            if e2 < dx: err += dx; y += sy

    def jit_compute_voronoi(owners, shared_positions, rows, cols):
        """
        NumPy Vectorized approximation for Voronoi.
        Computes 2D grid of distances to all agents and takes argmin.
        Much faster than Python loop, slower than Numba.
        """
        # Create grid of coordinates
        # Y, X = np.indices((rows, cols))
        
        # But for 50x50, calculating distance to N agents is fast.
        # shared_positions is (N, 2) array [x, y]
        # We need dist grid for each agent.
        
        # This is heavy memory: (N, rows, cols)
        # N ~ 5-10, rows/cols ~ 50. 10*50*50 = 25k floats. Tiny.
        
        Y, X = np.ogrid[:rows, :cols]
        
        min_dist = np.full((rows, cols), float('inf'))
        
        # owners is updated in place
        
        for i in range(len(shared_positions)):
            c = shared_positions[i, 0]
            r = shared_positions[i, 1]
            
            # Manhattan distance (to match BFS behavior)
            dist = np.abs(X - c) + np.abs(Y - r)
            
            # Mask where this agent is closer
            closer_mask = dist < min_dist
            owners[closer_mask] = i
            min_dist[closer_mask] = dist[closer_mask]
            
            # Tie breaking: if equal, current 'i' overwrites if we want higher ID priority?
            # Or use stable update.
            # Here it's simple greedy update.
            
        return owners
