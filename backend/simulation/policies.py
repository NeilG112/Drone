import random
import numpy as np

class NavigationPolicy:
    def select_action(self, agent):
        """Returns (dx, dy) tuple."""
        raise NotImplementedError

class RandomWalk(NavigationPolicy):
    def select_action(self, agent):
        # 0: Up, 1: Right, 2: Down, 3: Left
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        
        # Simple heuristic: try not to hit known walls
        valid_moves = []
        for dx, dy in moves:
            nx, ny = agent.x + dx, agent.y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                 # If unknown or free, it's a valid candidate
                 # We avoid known obstacles (1)
                if agent.belief_map[ny, nx] != 1:
                    valid_moves.append((dx, dy))
        
        if not valid_moves:
             return (0, 0) # Stay put when no safe candidate
             
        return random.choice(valid_moves)

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


class WallFollow(NavigationPolicy):
    def __init__(self):
        self.dir_idx = 0 # 0: Up, 1: Right, 2: Down, 3: Left
        self.moves = [(0, -1), (1, 0), (0, 1), (-1, 0)] 
        
    def select_action(self, agent):
        # Right-hand rule logic
        # Check right side relative to current direction
        right_idx = (self.dir_idx + 1) % 4
        dx, dy = self.moves[right_idx]
        rx, ry = agent.x + dx, agent.y + dy
        
        is_right_open = False
        if 0 <= rx < agent.width and 0 <= ry < agent.height:
             if agent.belief_map[ry, rx] != 1: # If not known obstacle
                 is_right_open = True
        
        if is_right_open:
            # Turn right and move
            self.dir_idx = right_idx
            return self.moves[self.dir_idx]
            
        # Try moving forward
        fdx, fdy = self.moves[self.dir_idx]
        fx, fy = agent.x + fdx, agent.y + fdy
        if 0 <= fx < agent.width and 0 <= fy < agent.height and agent.belief_map[fy, fx] != 1:
            return (fdx, fdy)
            
        # Wall in front, turn left (counter-clockwise)
        self.dir_idx = (self.dir_idx - 1) % 4
        return (0, 0) # Wait one turn to rotate

POLICIES = {
    'random': RandomWalk,
    'frontier': FrontierExploration,
    'wall_follow': WallFollow
}

def get_policy(name):
    return POLICIES.get(name, RandomWalk)()
