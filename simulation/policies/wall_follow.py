from .base import NavigationPolicy

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
