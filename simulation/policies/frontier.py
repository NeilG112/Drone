import random
from .base import NavigationPolicy

class FrontierExploration(NavigationPolicy):
    def select_action(self, agent):
        # Find nearest unknown cell (frontier)
        # BFS to find nearest -1 in belief map
        
        start = (agent.x, agent.y)
        queue = [(start, [])]
        visited = {start}
        
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)] # Up, Right, Down, Left
        
        while queue:
            (curr_x, curr_y), path = queue.pop(0)
            
            # Check if this node is adjacent to an unknown cell (frontier edge)
            is_frontier = False
            for dx, dy in moves:
                nx, ny = curr_x + dx, curr_y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        is_frontier = True
                        break
            
            if is_frontier:
                # If we are at the frontier, we need to take the first step of the path
                if not path:
                    # We are already at a frontier, pick a move into the unknown
                     for dx, dy in moves:
                        nx, ny = agent.x + dx, agent.y + dy
                        if 0 <= nx < agent.width and 0 <= ny < agent.height:
                            if agent.belief_map[ny, nx] == -1:
                                return (dx, dy)
                     return random.choice(moves) # Should not happen if is_frontier check passed
                
                return path[0]

            # Expand search through free space
            for dx, dy in moves:
                nx, ny = curr_x + dx, curr_y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if (nx, ny) not in visited and agent.belief_map[ny, nx] == 0:
                        visited.add((nx, ny))
                        new_path = list(path)
                        new_path.append((dx, dy))
                        queue.append(((nx, ny), new_path))
        
        # If no frontier found (map fully explored?), safe fallback
        return (0, 0)
