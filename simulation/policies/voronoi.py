import numpy as np
import random
from simulation.policies.base import NavigationPolicy
from simulation.utils.pathfinding import astar_path
try:
    from simulation.utils.jit_math import jit_compute_voronoi
    HAS_JIT = True
except ImportError:
    HAS_JIT = False

class VoronoiPartitionPolicy(NavigationPolicy):
    def __init__(self):
        super().__init__()
        
    def select_action(self, agent):
        # 0. Check Battery / RTB
        start_x, start_y = agent.path[0]
        dist_to_home = abs(agent.x - start_x) + abs(agent.y - start_y)
        if agent.battery < (dist_to_home * agent.energy_cost_move * 1.5) + 20:
             path = astar_path((agent.x, agent.y), (start_x, start_y), agent.belief_map, agent.width, agent.height)
             if path:
                 return path[0]
             return (0, 0)
             
        # 1. Compute/Approximate Voronoi Regions
        # We need to know which cells "belong" to this agent.
        # This requires knowing positions of ALL agents.
        # agent.shared_positions contains list of {x,y} for all agents (if communicated)
        
        my_region_mask = self._compute_local_voronoi(agent)
        
        # 2. Find Frontiers within My Region
        my_frontiers = self._find_frontiers_in_region(agent, my_region_mask)
        
        # 3. Select Action
        if my_frontiers:
            # Go to nearest frontier in my region
            best_frontier = self._get_nearest_frontier(agent, my_frontiers)
            if best_frontier:
                 path = astar_path((agent.x, agent.y), best_frontier, agent.belief_map, agent.width, agent.height)
                 if path:
                     return path[0]
                     
        # 4. Fallback: If no frontiers in my region (I'm done?), help others or random
        # Expand consistency: Look for ANY frontier if mine are done? 
        # For now, random walk to find more info
        return self._random_walk(agent)

    def _compute_local_voronoi(self, agent):
        """
        Computes a mask where 1 = belongs to me, 0 = belongs to others.
        Uses Multi-Source BFS.
        """
        rows, cols = agent.height, agent.width
        owners = np.full((rows, cols), -1, dtype=int)
        
        if HAS_JIT:
            # Prepare data for numba
            # shared_positions is list of dicts. Connect to simple array [[c, r], ...]
            # Assuming agent_id matches index
            n_agents = len(agent.shared_positions)
            pos_array = np.full((n_agents, 2), -1, dtype=np.int32)
            
            for i, pos in enumerate(agent.shared_positions):
                if pos:
                    pos_array[i, 0] = int(pos['x']) # Col
                    pos_array[i, 1] = int(pos['y']) # Row
            
            owners = jit_compute_voronoi(owners, pos_array, rows, cols)
            return (owners == agent.agent_id)
            
        # Fallback: Slow Python BFS
        # Sources: All agents
        queue = []
        for i, pos_dict in enumerate(agent.shared_positions):
            # pos_dict is {'x':..., 'y':...} or None
            # The list index implicitly assumes agent_id match
             if pos_dict:
                 x, y = int(pos_dict['x']), int(pos_dict['y'])
                 if 0 <= x < cols and 0 <= y < rows:
                     owners[y, x] = i
                     queue.append((x, y, i))
        
        # Shuffle queue to randomise expansion order for fairness?
        # Standard BFS queue is fine for approx voronoi (Manhattan)
        
        visited = set([(x, y) for x, y, i in queue])
        
        head = 0
        while head < len(queue):
            x, y, owner_id = queue[head]
            head += 1
            
            # Expand
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                
                if 0 <= nx < cols and 0 <= ny < rows:
                    if (nx, ny) not in visited:
                        # Tie-breaking logic: 
                        # In standard BFS, first come first serve. 
                        # If queue was populated 0..N, then 0 has slight advantage in ties.
                        # Fine for this simulation.
                        visited.add((nx, ny))
                        owners[ny, nx] = owner_id
                        queue.append((nx, ny, owner_id))
                        
        return (owners == agent.agent_id)

    def _find_frontiers_in_region(self, agent, mask):
        # Scan cells where mask is True AND is frontier
        frontiers = []
        rows, cols = agent.height, agent.width
        
        # Optimization: Only scan known frontiers?
        # But we don't have a list of frontiers pre-calculated.
        # Scan bounding box of free space?
        # Full scan is 2500 for 50x50, ok.
        
        for y in range(rows):
            for x in range(cols):
                if mask[y, x]: # In my region
                    # Is it a frontier? (Unknown neighbor to free)
                    # Actually standard definition: Free cell adjacent to unknown.
                    if agent.belief_map[y, x] == 0:
                        # Check neighbors
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < cols and 0 <= ny < rows:
                                if agent.belief_map[ny, nx] == -1:
                                    frontiers.append((x, y))
                                    break
        return frontiers

    def _get_nearest_frontier(self, agent, frontiers):
        min_dist = float('inf')
        best = None
        for fx, fy in frontiers:
            d = abs(agent.x - fx) + abs(agent.y - fy)
            if d < min_dist:
                min_dist = d
                best = (fx, fy)
        return best

    def _random_walk(self, agent):
         moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
         valid_moves = []
         for dx, dy in moves:
             nx, ny = agent.x + dx, agent.y + dy
             if 0 <= nx < agent.width and 0 <= ny < agent.height:
                 if agent.belief_map[ny, nx] != 1:
                     valid_moves.append((dx, dy))
         if valid_moves:
             return random.choice(valid_moves)
         return (0, 0)
