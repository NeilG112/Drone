import random
from .base import NavigationPolicy

class GenericPolicy(NavigationPolicy):
    def __init__(self):
        # Optional: you can initialize parameters like grid size, obstacles, etc.
        pass

    def select_action(self, agent):
        """
        Select an action for the agent based on some condition.
        
        The agent object should have at least the following properties:
        - agent.x, agent.y: Current position.
        - agent.width, agent.height: Dimensions of the environment.
        - agent.belief_map (or any attribute): A belief map or state representation (could be used for obstacles, goals, etc.)
        
        This is a placeholder for a generic algorithm. Modify this method to suit specific needs.
        """
        
        # Example of a set of possible actions or moves
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # Up, Right, Down, Left
        
        # Example of a condition: modify this block to fit the algorithm's logic
        valid_moves = []
        for dx, dy in moves:
            nx, ny = agent.x + dx, agent.y + dy
            
            # Modify this condition based on your policy (e.g., avoiding walls, obstacles, etc.)
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] != 1:  # Placeholder check (e.g., avoid obstacles)
                    valid_moves.append((dx, dy))
        
        # If there are no valid moves, make the agent stay in place
        if not valid_moves:
            return (0, 0)  # Stay put
        
        # Modify this return to suit the action-selection logic of your policy
        return random.choice(valid_moves)  # Example: randomly pick one valid move
