import heapq
import numpy as np

def astar_path(start, goal, belief_map, width, height, allow_diagonal=False):
    """
    Finds a path from start to goal using A* algorithm on the belief_map.
    belief_map: 2D array where 1 is obstacle, 0 is free, -1 is unknown.
    Assumes unknown is traversable (optimistic).
    Returns: list of (dx, dy) steps to reach goal, or [] if no path.
    """
    sx, sy = int(start[0]), int(start[1])
    gx, gy = int(goal[0]), int(goal[1])
    
    # Priority Queue: (f_score, x, y)
    open_set = []
    heapq.heappush(open_set, (0, sx, sy))
    
    came_from = {}
    g_score = { (sx, sy): 0 }
    f_score = { (sx, sy): abs(sx - gx) + abs(sy - gy) }
    
    visited = set()
    
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if allow_diagonal:
        moves += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        
    while open_set:
        _, cx, cy = heapq.heappop(open_set)
        
        if (cx, cy) == (gx, gy):
            return reconstruct_path(came_from, (cx, cy), (sx, sy))
            
        visited.add((cx, cy))
        
        for dx, dy in moves:
            nx, ny = cx + dx, cy + dy
            
            # Bounds check
            if 0 <= nx < width and 0 <= ny < height:
                # Obstacle check (Unknown -1 is allowed, 1 is blocked)
                # Note: We treat -1 as free for optimistic planning.
                if belief_map[ny, nx] == 1:
                    continue
                    
                # Tentative G score
                move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                tentative_g = g_score[(cx, cy)] + move_cost
                
                if (nx, ny) not in g_score or tentative_g < g_score[(nx, ny)]:
                    came_from[(nx, ny)] = (cx, cy)
                    g_score[(nx, ny)] = tentative_g
                    h = abs(nx - gx) + abs(ny - gy) # Manhattan
                    f_score[(nx, ny)] = tentative_g + h
                    heapq.heappush(open_set, (f_score[(nx, ny)], nx, ny))
                    
    return [] # No path found

def reconstruct_path(came_from, current, start):
    path = []
    while current != start:
        prev = came_from.get(current)
        if not prev:
            break
        # Calculate step
        dx = current[0] - prev[0]
        dy = current[1] - prev[1]
        path.append((dx, dy))
        current = prev
    return path[::-1] # Reverse to get start->goal
