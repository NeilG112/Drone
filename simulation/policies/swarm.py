import random
import math
from .base import NavigationPolicy

class Swarm(NavigationPolicy):
    def select_action(self, agent):
        # 1. Find N nearest frontiers using BFS
        frontiers = self._find_nearest_frontiers(agent, limit=10)
        
        if not frontiers:
            return (0, 0)
            
        best_move = None
        
        # 2. Evaluate frontiers based on "ownership"
        # A frontier is "owned" by the drone closest to it.
        # Ties broken by agent_id.
        
        valid_frontier = None
        
        for f_pos, path in frontiers:
            is_mine = True
            my_dist = len(path)
            
            # Check against all other agents
            for i, other_pos in enumerate(agent.shared_positions):
                if i == agent.agent_id:
                    continue
                    
                # Estimate distance for other agent (Manhattan is fast)
                # Note: This implies free space. Actual path might be longer, 
                # but Manhattan is a good enough heuristic for "closer".
                other_dist = abs(other_pos['x'] - f_pos[0]) + abs(other_pos['y'] - f_pos[1])
                
                # If someone else is significantly closer, give it up
                if other_dist < my_dist:
                    is_mine = False
                    break
                
                # Tie-breaking: Lower ID wins
                if other_dist == my_dist and i < agent.agent_id:
                    is_mine = False
                    break
            
            if is_mine:
                # We found a target that we are the closest to!
                valid_frontier = path[0] if path else (0,0) # Should have path
                break
        
        # 3. Fallback: If all nearby frontiers are "owned" by others (e.g. we are trailing),
        # just go to the nearest one anyway to catch up / contribute.
        if valid_frontier:
            return valid_frontier
        else:
            # Just pick the nearest one (first in list)
            if frontiers[0][1]:
                return frontiers[0][1][0]
            return (0, 0)

    def _find_nearest_frontiers(self, agent, limit=5):
        """BFS to find the 'limit' nearest frontier cells."""
        start = (agent.x, agent.y)
        queue = [(start, [])]
        visited = {start}
        
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)] # Up, Right, Down, Left
        
        found_frontiers = [] # List of (pos, path_to_it)
        
        while queue:
            (curr_x, curr_y), path = queue.pop(0)
            
            # Optimization: If path is too long, stop search (local horizon)
            if len(path) > 50 and found_frontiers: 
                break
                
            # Check if frontier
            is_frontier = False
            for dx, dy in moves:
                nx, ny = curr_x + dx, curr_y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        is_frontier = True
                        break
            
            if is_frontier:
                # Found one!
                # Note: The frontier cell itself is 'curr', which is free space but touches -1.
                # Actually, strictly usually we want to move INTO -1? 
                # But moving adjacent to it discloses it. 
                # Let's say target is the free cell adjacent to unknown.
                found_frontiers.append(((curr_x, curr_y), path))
                
                if len(found_frontiers) >= limit:
                    break
            
            # Expand
            random.shuffle(moves) # Randomize expansion for variety
            for dx, dy in moves:
                nx, ny = curr_x + dx, curr_y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if (nx, ny) not in visited and agent.belief_map[ny, nx] == 0:
                        visited.add((nx, ny))
                        new_path = list(path)
                        new_path.append((dx, dy))
                        queue.append(((nx, ny), new_path))
                        
        return found_frontiers
