import numpy as np
import math
import random
from ..base import NavigationPolicy
from collections import deque



class SYSTEMATICCOMPLEXCOVERAGE(NavigationPolicy):
    """
    Super-optimized for 100x100, 67% obstacles, 500 steps.
    Uses minimal computation per step.
    200 runs: 
    Sucess Rate: 32.5%
    Average steps: 194.86
    Average coverage: 7.8%
    Search Efficiency: 0.783
    Average turns: 70.55
    1000 runs:
    Sucess Rate: 29.1%
    Average steps: 194.5
    Average coverage: 7.9%
    Search Efficiency: 0.789
    Average turns: 72.16
    10000runs:
    Sucess Rate: 27.93%
    Average steps: 194.04
    Average coverage: 8%
    Search Efficiency: 0.797
    Average turns: 73.75

    """
    
    def __init__(self):
        # Simple tracking
        self.visited = {}
        self.direction = (1, 0)  # Start moving right
        self.wall_follow_mode = False
        self.stuck_counter = 0
        
        # Pre-computed directions
        self.dir_order_right = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # Up, Right, Down, Left
        self.dir_order_left = [(0, -1), (-1, 0), (0, 1), (1, 0)]   # Up, Left, Down, Right
        
    def select_action(self, agent):
        current_pos = (int(agent.x), int(agent.y))
        self.visited[current_pos] = self.visited.get(current_pos, 0) + 1
        
        # 1. Immediate target check (fastest possible)
        for dx, dy in self.dir_order_right:
            nx, ny = current_pos[0] + dx, current_pos[1] + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 2:
                    return (dx, dy)
        
        # 2. Get valid moves
        valid_moves = []
        for dx, dy in self.dir_order_right:
            nx, ny = current_pos[0] + dx, current_pos[1] + dy
            if self._is_valid(agent, nx, ny):
                valid_moves.append((dx, dy))
        
        if not valid_moves:
            return (0, 0)
        
        # 3. If in wall follow mode, continue
        if self.wall_follow_mode:
            action = self._continue_wall_follow(agent, current_pos, valid_moves)
            if action != (0, 0):
                return action
            self.wall_follow_mode = False
        
        # 4. Score moves (ultra-fast scoring)
        best_move = None
        best_score = -999
        
        for dx, dy in valid_moves:
            nx, ny = current_pos[0] + dx, current_pos[1] + dy
            new_pos = (nx, ny)
            
            score = 0
            
            # A. Never visited: +100
            if new_pos not in self.visited:
                score += 100
            
            # B. Continue same direction: +30
            if (dx, dy) == self.direction:
                score += 30
            
            # C. Leads to area with more options: +20 per additional exit
            future_exits = self._count_exits(agent, nx, ny)
            score += 10 * future_exits
            
            # D. Avoid revisiting: -10 per visit
            score -= 10 * self.visited.get(new_pos, 0)
            
            # E. Random tie-breaker
            score += random.randint(0, 5)
            
            if score > best_score:
                best_score = score
                best_move = (dx, dy)
        
        # 5. Update state
        if best_move:
            self.direction = best_move
            self.stuck_counter = 0
        else:
            self.stuck_counter += 1
        
        # 6. If stuck, enter wall follow mode
        if self.stuck_counter > 5:
            self.wall_follow_mode = True
            self.stuck_counter = 0
        
        return best_move or valid_moves[0]
    
    def _continue_wall_follow(self, agent, current_pos, valid_moves):
        """Simple right-hand rule wall following"""
        x, y = current_pos
        
        # Find current direction index
        if self.direction in self.dir_order_right:
            idx = self.dir_order_right.index(self.direction)
        else:
            idx = 1  # Default to right
        
        # Try forward, then right, then left, then back
        for offset in [0, 1, 3, 2]:
            test_idx = (idx + offset) % 4
            dx, dy = self.dir_order_right[test_idx]
            
            if (dx, dy) in valid_moves:
                return (dx, dy)
        
        return (0, 0)
    
    def _count_exits(self, agent, x, y):
        """Count valid exits from a position"""
        count = 0
        for dx, dy in self.dir_order_right:
            nx, ny = x + dx, y + dy
            if self._is_valid(agent, nx, ny):
                count += 1
        return count
    
    def _is_valid(self, agent, x, y):
        """Fast validity check"""
        return (0 <= x < agent.width and 
                0 <= y < agent.height and 
                agent.belief_map[y, x] != 1)