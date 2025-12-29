import numpy as np
import random
from ..base import NavigationPolicy
import math

"""
Sucess Rate: 35%
Average steps: 218.17
Average coverage: 8.6%
Search Efficiency: 0.79
Average turns: 119.62
Pretty decent results for a single algorithm and it is relatively fast."""

class OptimizedComplexNavigation(NavigationPolicy):
    """
    Single optimized algorithm that uses complex numbers for efficient navigation.
    Key features:
    1. Simple complex arithmetic for direction selection
    2. Minimal computational overhead
    3. Balanced exploration vs exploitation
    4. Memory-efficient visited tracking
    """
    
    def __init__(self, exploration_strength=0.7, momentum=0.6):
        self.exploration_strength = exploration_strength
        self.momentum = momentum
        
        # Complex state variables
        self.current_direction = 1 + 0j  # Start moving right
        self.visited_positions = set()
        
        # Exploration state
        self.steps_without_progress = 0
        self.last_visit_count = 0
        
    def select_action(self, agent):
        current_pos = (int(agent.x), int(agent.y))
        self.visited_positions.add(current_pos)
        
        # 1. Quick check for immediate targets (highest priority)
        target_action = self._check_immediate_targets(agent)
        if target_action != (0, 0):
            self.steps_without_progress = 0
            self.current_direction = complex(target_action[0], target_action[1])
            return target_action
        
        # 2. Get all valid moves
        valid_moves = []
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = int(agent.x + dx), int(agent.y + dy)
            if (0 <= nx < agent.width and 0 <= ny < agent.height and 
                agent.belief_map[ny, nx] != 1):
                valid_moves.append((dx, dy))
        
        if not valid_moves:
            return (0, 0)
        
        # 3. Score each move using complex-valued evaluation
        best_move = None
        best_score = -float('inf')
        current_z = complex(agent.x, agent.y)
        
        for dx, dy in valid_moves:
            new_z = complex(agent.x + dx, agent.y + dy)
            new_pos = (int(new_z.real), int(new_z.imag))
            
            # Complex scoring formula:
            # score = exploration_value + momentum_alignment + frontier_bonus
            
            score = 0.0
            
            # Exploration value (prefer unvisited cells)
            if new_pos not in self.visited_positions:
                score += 3.0 * self.exploration_strength
            else:
                # Slight penalty for revisiting
                score -= 0.5
            
            # Momentum alignment (continue in similar direction)
            move_vector = complex(dx, dy)
            momentum_alignment = (self.current_direction.real * move_vector.real + 
                                 self.current_direction.imag * move_vector.imag)
            score += self.momentum * momentum_alignment
            
            # Frontier bonus (if this move reveals new unknown cells)
            if self._reveals_unknown(agent, new_z):
                score += 2.0
            
            # Avoid oscillating between two positions
            if len(valid_moves) > 1 and self._is_backtrack(new_pos):
                score -= 1.5
            
            # Add small random component to break ties
            score += random.uniform(0, 0.1)
            
            if score > best_score:
                best_score = score
                best_move = (dx, dy)
        
        # 4. If stuck, occasionally force exploration
        self.steps_without_progress += 1
        if self.steps_without_progress > 12:
            # Force move to least visited option
            least_visited_move = min(valid_moves, 
                                   key=lambda move: self._get_visit_count(agent, move))
            best_move = least_visited_move
            self.steps_without_progress = 0
        
        # 5. Update current direction (complex momentum)
        if best_move:
            dx, dy = best_move
            self.current_direction = (0.7 * self.current_direction + 
                                    0.3 * complex(dx, dy))
            # Normalize to unit complex number
            mag = math.sqrt(self.current_direction.real**2 + self.current_direction.imag**2)
            if mag > 0:
                self.current_direction = complex(self.current_direction.real/mag, 
                                               self.current_direction.imag/mag)
        
        return best_move or (0, 0)
    
    def _check_immediate_targets(self, agent):
        """Fast check for targets in immediate vicinity"""
        x, y = int(agent.x), int(agent.y)
        
        # Check immediate neighbors (4 directions)
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 2:
                    return (dx, dy)
        
        # Check diagonals if no immediate target found
        for dx, dy in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 2:
                    # Move toward it (one axis at a time)
                    if dx != 0:
                        return (1 if dx > 0 else -1, 0)
                    else:
                        return (0, 1 if dy > 0 else -1)
        
        return (0, 0)
    
    def _reveals_unknown(self, agent, position_z):
        """Check if moving to position reveals new unknown cells"""
        x, y = int(position_z.real), int(position_z.imag)
        
        # Check 3x3 area around new position
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        return True
        return False
    
    def _get_visit_count(self, agent, move):
        """Get how many times target cell has been visited"""
        dx, dy = move
        nx, ny = int(agent.x + dx), int(agent.y + dy)
        target_pos = (nx, ny)
        # Count visits (1 if not visited yet)
        return 1 if target_pos not in self.visited_positions else 2
    
    def _is_backtrack(self, new_pos):
        """Check if moving to a recently visited position"""
        # Simple check: if we have visited positions stored, check recent ones
        if hasattr(self, 'last_positions'):
            return new_pos in self.last_positions
        return False