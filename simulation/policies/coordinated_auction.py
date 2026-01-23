import numpy as np
import random
from collections import deque
from simulation.policies.base import NavigationPolicy
from simulation.utils.pathfinding import astar_path

class CoordinatedUtilityAuctionPolicy(NavigationPolicy):
    def __init__(self):
        super().__init__()
        # Parameters
        self.explore_weight = 1.0
        self.distance_weight = 0.5
        self.overlap_weight = 2.0
        self.battery_weight = 10.0 # High penalty for dying
        
        self.auction_interval = 5
        self.last_auction_step = 0
        
        # State
        self.current_assignment = None # (x, y) or None
        self.assigned_frontier_id = None
        
    def select_action(self, agent):
        # 1. Update Internal State (Maps are updated by Agent.sense)
        # 2. Check Battery / Survival
        if self._should_retreat(agent):
             return self._get_move_towards_base(agent)
             
        # 3. Check Victim Tracking (High Priority)
        # If we have a high prob victim, go there.
        victim_target = self._scan_for_victims(agent)
        if victim_target:
            return self._plan_path(agent, victim_target)
            
        # 4. Auction / Frontier Assignment
        # Run auction logic if needed or if current assignment is invalid/done
        if self._needs_reassignment(agent):
             self._run_auction(agent)
             
        # 5. Execution
        if self.current_assignment:
            dx, dy = self._plan_path(agent, self.current_assignment)
            if dx == 0 and dy == 0:
                 # Stuck or reached?
                 # If we are not at target, we are stuck.
                 ax, ay = self.current_assignment
                 if ax != int(agent.x) or ay != int(agent.y):
                     # Stuck! Drop assignment
                     self.current_assignment = None
                     return self._random_walk(agent)
            return (dx, dy)
            
        # Fallback: Random robust walk
        return self._random_walk(agent)
    
    def _should_retreat(self, agent):
        start_x, start_y = agent.path[0]
        dist = abs(agent.x - start_x) + abs(agent.y - start_y)
        # Margin of 20 units
        if agent.battery < (dist * agent.energy_cost_move * 1.5) + 20:
            return True
        return False
        
    def _get_move_towards_base(self, agent):
        start_x, start_y = agent.path[0]
        # Use A* logic directly
        path = astar_path((agent.x, agent.y), (start_x, start_y), agent.belief_map, agent.width, agent.height)
        if path:
            return path[0]
        return (0, 0)
        
    def _get_move_towards_target(self, agent, target):
        tx, ty = target
        # Simple greedy for now, or BFS/A*
        # Use simple greedy to save compute for this step
        if agent.x < tx: dx = 1
        elif agent.x > tx: dx = -1
        else: dx = 0
        
        if agent.y < ty: dy = 1
        elif agent.y > ty: dy = -1
        else: dy = 0
        
        # Check collision
        return (dx, dy) # Need better pathfinding respecting obstacles
        
    def _scan_for_victims(self, agent):
        # Scan victim_prob_map
        # If any cell > 0.8 (threshold), return it
        # Prefer closest
        ys, xs = np.where(agent.victim_prob_map > 0.8)
        if len(xs) > 0:
            # Find closest
            min_dist = float('inf')
            best = None
            for x, y in zip(xs, ys):
                d = abs(agent.x - x) + abs(agent.y - y)
                if d < min_dist:
                    min_dist = d
                    best = (x, y)
            return best
        return None
        
    def _needs_reassignment(self, agent):
        # If no assignment, yes
        if not self.current_assignment:
            return True
        # If assignment reached, yes
        ax, ay = self.current_assignment
        if int(agent.x) == ax and int(agent.y) == ay:
            return True
        # If assignment is no longer unexplored (frontier cleared), yes
        if agent.belief_map[ay, ax] != -1: # It is known now
             return True
        return False
        
    def _run_auction(self, agent):
        # 1. Identify Frontiers
        cell_frontiers = self._find_frontiers(agent)
        if not cell_frontiers:
            self.current_assignment = None
            return

        # 2. Cluster Frontiers
        clusters = self._cluster_frontiers(cell_frontiers)
        
        # 3. Calculate Utility for each Cluster
        # My Bids
        my_bids = []
        for cluster in clusters:
            u = self._calculate_utility(agent, cluster)
            my_bids.append((u, cluster))
            
        # Sort by Utility
        my_bids.sort(key=lambda x: x[0], reverse=True)
        
        # 4. Resolve: Pick best logic
        if my_bids:
             self.current_assignment = my_bids[0][1]['centroid']
        else:
             self.current_assignment = None

    def _cluster_frontiers(self, cells):
        # Simple BFS clustering
        clusters = []
        visited = set()
        
        for cell in cells:
            if cell in visited:
                continue
                
            # New cluster
            cluster_cells = []
            queue = [cell]
            visited.add(cell)
            while queue:
                curr = queue.pop(0)
                cluster_cells.append(curr)
                cx, cy = curr
                
                # Check neighbors
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if (nx, ny) in cells and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
            
            # Compute centroid
            sum_x = sum(c[0] for c in cluster_cells)
            sum_y = sum(c[1] for c in cluster_cells)
            centroid = (int(sum_x / len(cluster_cells)), int(sum_y / len(cluster_cells)))
            
            clusters.append({
                'centroid': centroid,
                'size': len(cluster_cells),
                'cells': cluster_cells
            })
            
        return clusters

    def _find_frontiers(self, agent):
        # Cells that are UNKNOWN (-1) and adjacent to FREE (0)
        # Expensive to scan whole map?
        # Scan only free cells?
        # Scan known map
        rows, cols = agent.belief_map.shape
        frontiers = []
        
        # Optimization: Maintain frontier set incrementally? 
        # For now, full scan (map is small 50x50 usually)
        for y in range(rows):
            for x in range(cols):
                if agent.belief_map[y, x] == 0: # Free
                    # Check neighbors for unknown
                    for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                        ny, nx = y+dy, x+dx
                        if 0 <= ny < rows and 0 <= nx < cols:
                            if agent.belief_map[ny, nx] == -1:
                                frontiers.append((nx, ny))
        return list(set(frontiers)) # Unique

    def _calculate_utility(self, agent, cluster):
        # Utility = Size - Dist - Overlap
        fx, fy = cluster['centroid']
        size = cluster['size']
        
        dist = abs(agent.x - fx) + abs(agent.y - fy)
        
        # Overlap Penalty: Is a neighbor closer?
        overlap = 0.0
        for nid in agent.connected_neighbors:
             # Need neighbor pos.
             # Agent.shared_positions has everyone.
             npos = agent.shared_positions[nid]
             ndist = abs(npos['x'] - fx) + abs(npos['y'] - fy)
             
             # Tie-breaking for stacked agents:
             # If distance is equal, lower ID yields to higher ID (or vice versa).
             # Let's say lower ID has priority? No, usually random or fixed.
             # If I am Agent 0, neighbor is Agent 1.
             # Dist same.
             # I check: is 1 closer? No.
             # Agent 1 checks: is 0 closer? No.
             # Both take it. Bad.
             # New Logic:
             # If ndist < dist: penalty.
             # If ndist == dist and nid < agent.agent_id: penalty (I yield to smaller ID)
             # Wait, if I yield to smaller ID, then smaller ID must NOT yield to me.
             # smaller ID check: my_id > nid (True). He does NOT yield. I yield.
             # Correct.
             
             if ndist < dist or (ndist == dist and nid < agent.agent_id):
                 overlap += 1.0 # Penalize if someone else is closer or equal-dist-but-senior
                 
        return (self.explore_weight * size) - (self.distance_weight * dist) - (self.overlap_weight * overlap * 10)

    def _plan_path(self, agent, target):
        path = astar_path((agent.x, agent.y), target, agent.belief_map, agent.width, agent.height)
        if path:
            return path[0]
        return (0, 0)
        
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
