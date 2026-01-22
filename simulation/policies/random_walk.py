import random
from .base import NavigationPolicy

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
