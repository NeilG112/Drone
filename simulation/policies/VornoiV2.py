import numpy as np
import random
from simulation.policies.base import NavigationPolicy
from simulation.utils.pathfinding import astar_path
try:
    from simulation.utils.jit_math import jit_compute_voronoi
    HAS_JIT = True
except ImportError:
    HAS_JIT = False

class VoronoiPartitionPolicyV2(NavigationPolicy):
    def __init__(self, safety_margin=1.5, rtb_threshold=0.4):
        """
        Args:
            safety_margin: Multiply energy cost by this for safety buffer (default 1.5 = 50% margin)
            rtb_threshold: Force RTB when battery drops below this fraction of max (default 0.4 = 40%)
        """
        super().__init__()
        self.safety_margin = safety_margin
        self.rtb_threshold = rtb_threshold
        self.returning_home = False  # Track RTB state
        
    def select_action(self, agent):
        start_x, start_y = agent.path[0]
        dist_to_home = abs(agent.x - start_x) + abs(agent.y - start_y)
        energy_needed_home = dist_to_home * agent.energy_cost_move * self.safety_margin
        
        # CRITICAL CHECK 1: Are we already at home? Reset RTB flag
        if agent.x == start_x and agent.y == start_y:
            self.returning_home = False
        
        # CRITICAL CHECK 2: Battery below RTB threshold? FORCE return home
        max_battery = getattr(agent, 'max_battery', 100)  # Fallback if not defined
        if agent.battery < max_battery * self.rtb_threshold:
            self.returning_home = True
        
        # CRITICAL CHECK 3: Not enough battery to make it home? EMERGENCY RTB
        if agent.battery <= energy_needed_home:
            self.returning_home = True
            
        # If in RTB mode, ONLY navigate home (no exploration)
        if self.returning_home:
            if dist_to_home == 0:
                # We're home, mission accomplished (will reset flag above on next call)
                return (0, 0)
            path = astar_path((agent.x, agent.y), (start_x, start_y), agent.belief_map, agent.width, agent.height)
            if path:
                return path[0]
            # Path blocked? Try direct movement
            dx = np.sign(start_x - agent.x) if start_x != agent.x else 0
            dy = np.sign(start_y - agent.y) if start_y != agent.y else 0
            if dx != 0 or dy != 0:
                return (int(dx), int(dy))
            return (0, 0)
             
        # 1. Compute Voronoi Regions - divide the house among drones
        my_region_mask = self._compute_local_voronoi(agent)
        
        # 2. Find ALL frontiers in my region
        my_frontiers = self._find_frontiers_in_region(agent, my_region_mask)
        
        # 3. Filter frontiers: Only keep SAFE ones (can reach + return)
        safe_frontiers = self._filter_safe_frontiers(agent, my_frontiers, start_x, start_y)
        
        # 4. Select best safe frontier
        if safe_frontiers:
            best_frontier = self._get_nearest_frontier(agent, safe_frontiers)
            if best_frontier:
                path = astar_path((agent.x, agent.y), best_frontier, agent.belief_map, agent.width, agent.height)
                if path:
                    return path[0]
                     
        # 5. Fallback: No safe frontiers in my region
        # This means either: (a) my region is fully explored, or (b) battery too low for any frontier
        # Try to explore any remaining frontier if battery allows
        all_frontiers = self._find_all_frontiers(agent)
        safe_all_frontiers = self._filter_safe_frontiers(agent, all_frontiers, start_x, start_y)
        
        if safe_all_frontiers:
            best_frontier = self._get_nearest_frontier(agent, safe_all_frontiers)
            if best_frontier:
                path = astar_path((agent.x, agent.y), best_frontier, agent.belief_map, agent.width, agent.height)
                if path:
                    return path[0]
        
        # 6. Last resort: Return home or random walk in safe radius
        # At this point we have good battery but nowhere useful to go
        # Do a safe random walk to potentially discover new frontiers
        return self._safe_random_walk(agent, start_x, start_y)

    def _filter_safe_frontiers(self, agent, frontiers, home_x, home_y):
        """
        Only return frontiers that the drone can reach AND return home from.
        Uses Manhattan distance as conservative estimate.
        """
        safe = []
        current_battery = agent.battery
        
        for fx, fy in frontiers:
            # Estimate: distance to frontier + distance from frontier to home
            dist_to_frontier = abs(agent.x - fx) + abs(agent.y - fy)
            dist_frontier_to_home = abs(fx - home_x) + abs(fy - home_y)
            
            total_dist = dist_to_frontier + dist_frontier_to_home
            energy_needed = total_dist * agent.energy_cost_move * self.safety_margin
            
            if current_battery > energy_needed:
                safe.append((fx, fy))
                
        return safe

    def _compute_local_voronoi(self, agent):
        """
        Computes a mask where 1 = belongs to me, 0 = belongs to others.
        Uses Multi-Source BFS for Manhattan distance Voronoi.
        """
        rows, cols = agent.height, agent.width
        owners = np.full((rows, cols), -1, dtype=int)
        
        if HAS_JIT:
            # Use optimized numba version
            n_agents = len(agent.shared_positions)
            pos_array = np.full((n_agents, 2), -1, dtype=np.int32)
            
            for i, pos in enumerate(agent.shared_positions):
                if pos:
                    pos_array[i, 0] = int(pos['x'])
                    pos_array[i, 1] = int(pos['y'])
            
            owners = jit_compute_voronoi(owners, pos_array, rows, cols)
            return (owners == agent.agent_id)
            
        # Fallback: Python BFS
        queue = []
        for i, pos_dict in enumerate(agent.shared_positions):
            if pos_dict:
                x, y = int(pos_dict['x']), int(pos_dict['y'])
                if 0 <= x < cols and 0 <= y < rows:
                    owners[y, x] = i
                    queue.append((x, y, i))
        
        visited = set([(x, y) for x, y, i in queue])
        
        head = 0
        while head < len(queue):
            x, y, owner_id = queue[head]
            head += 1
            
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                
                if 0 <= nx < cols and 0 <= ny < rows:
                    if (nx, ny) not in visited:
                        visited.add((nx, ny))
                        owners[ny, nx] = owner_id
                        queue.append((nx, ny, owner_id))
                        
        return (owners == agent.agent_id)

    def _find_frontiers_in_region(self, agent, mask):
        """Find frontier cells (free cells adjacent to unknown) within my Voronoi region."""
        frontiers = []
        rows, cols = agent.height, agent.width
        
        for y in range(rows):
            for x in range(cols):
                if mask[y, x] and agent.belief_map[y, x] == 0:
                    # Free cell in my region - check if it borders unknown
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < cols and 0 <= ny < rows:
                            if agent.belief_map[ny, nx] == -1:
                                frontiers.append((x, y))
                                break
        return frontiers

    def _find_all_frontiers(self, agent):
        """Find ALL frontiers in the map (fallback when my region is done)."""
        frontiers = []
        rows, cols = agent.height, agent.width
        
        for y in range(rows):
            for x in range(cols):
                if agent.belief_map[y, x] == 0:
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < cols and 0 <= ny < rows:
                            if agent.belief_map[ny, nx] == -1:
                                frontiers.append((x, y))
                                break
        return frontiers

    def _get_nearest_frontier(self, agent, frontiers):
        """Get closest frontier by Manhattan distance."""
        min_dist = float('inf')
        best = None
        for fx, fy in frontiers:
            d = abs(agent.x - fx) + abs(agent.y - fy)
            if d < min_dist:
                min_dist = d
                best = (fx, fy)
        return best

    def _safe_random_walk(self, agent, home_x, home_y):
        """Random walk but only to cells we can return from."""
        moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        valid_moves = []
        
        for dx, dy in moves:
            nx, ny = agent.x + dx, agent.y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] != 1:  # Not obstacle
                    # Check if we can return from (nx, ny)
                    dist_home = abs(nx - home_x) + abs(ny - home_y)
                    energy_needed = (1 + dist_home) * agent.energy_cost_move * self.safety_margin
                    
                    if agent.battery > energy_needed:
                        valid_moves.append((dx, dy))
                        
        if valid_moves:
            return random.choice(valid_moves)
        return (0, 0)