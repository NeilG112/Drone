import numpy as np
import random
import math
from .base import NavigationPolicy
from collections import deque

class AdvancedMazeMaster(NavigationPolicy):
    """
    Advanced algorithm for 100x100 maps with 67% obstacles.
    Features:
    1. Sector-based exploration (divide map into 10x10 sectors)
    2. Memory of visited sectors to ensure complete coverage
    3. Targeted room searching (you said rooms are size ~15)
    4. Adaptive strategy switching
    """
    
    def __init__(self, sector_size=10, room_search_radius=15):
        # Exploration state
        self.visited_cells = {}
        self.visited_sectors = set()
        self.unexplored_sectors = set()
        self.sector_size = sector_size
        
        # Room detection
        self.room_search_radius = room_search_radius
        self.rooms_found = []
        self.room_search_mode = False
        self.current_room_target = None
        
        # Path optimization
        self.direction_history = deque(maxlen=5)
        self.recent_positions = deque(maxlen=15)
        self.stuck_counter = 0
        self.successful_exploration = 0
        
        # Target memory
        self.target_memory = {}
        self.last_target_found = 0
        
        # Performance tracking
        self.steps = 0
        self.mode = "EXPLORE"  # EXPLORE, ROOM_SEARCH, TARGET_CHASE
        
    def select_action(self, agent):
        self.steps += 1
        current_pos = (int(agent.x), int(agent.y))
        self.recent_positions.append(current_pos)
        
        # Update sector tracking
        current_sector = self._get_sector(current_pos)
        self.visited_sectors.add(current_sector)
        
        # PRIORITY 1: Immediate target (within 3 cells)
        target_action = self._find_immediate_target(agent)
        if target_action != (0, 0):
            self.mode = "TARGET_CHASE"
            self.last_target_found = self.steps
            return target_action
        
        # PRIORITY 2: If we recently saw a target, go to its last known location
        if self.steps - self.last_target_found < 50 and self.target_memory:
            best_target = max(self.target_memory.items(), key=lambda x: x[1])[0]
            return self._move_toward_target(agent, best_target)
        
        # PRIORITY 3: Every 20 steps, check for room patterns
        if self.steps % 20 == 0:
            room_action = self._detect_and_enter_room(agent, current_pos)
            if room_action != (0, 0):
                self.mode = "ROOM_SEARCH"
                return room_action
        
        # PRIORITY 4: Systematic sector exploration
        return self._sector_based_exploration(agent, current_pos)
    
    def _sector_based_exploration(self, agent, current_pos):
        """Explore systematically by visiting all sectors"""
        
        # Get current sector and neighboring sectors
        current_sector = self._get_sector(current_pos)
        
        # Find the nearest unexplored sector
        target_sector = self._find_nearest_unexplored_sector(current_sector)
        
        if target_sector:
            # Move toward the center of that sector
            sector_center = (
                target_sector[0] * self.sector_size + self.sector_size // 2,
                target_sector[1] * self.sector_size + self.sector_size // 2
            )
            return self._move_toward_with_obstacle_avoidance(agent, sector_center)
        
        # If all sectors visited, do local exploration
        return self._local_exploration(agent, current_pos)
    
    def _local_exploration(self, agent, current_pos):
        """Explore locally within current sector"""
        
        # Get all valid moves
        valid_moves = []
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = current_pos[0] + dx, current_pos[1] + dy
            if self._is_valid_move(agent, nx, ny):
                valid_moves.append((dx, dy, nx, ny))
        
        if not valid_moves:
            return (0, 0)
        
        # Score moves based on multiple factors
        best_score = -9999
        best_move = valid_moves[0][:2]
        
        for dx, dy, nx, ny in valid_moves:
            new_pos = (nx, ny)
            score = 0
            
            # 1. UNVISITED CELL BONUS (Highest priority)
            if new_pos not in self.visited_cells:
                score += 100
            else:
                # Penalize revisiting
                score -= self.visited_cells.get(new_pos, 0) * 15
            
            # 2. DIRECTION CONTINUITY (smooth movement)
            if self.direction_history:
                last_dx, last_dy = self.direction_history[-1]
                if (dx, dy) == (last_dx, last_dy):
                    score += 30
            
            # 3. REVEALS NEW AREAS (check 5x5 area)
            new_area_revealed = self._count_new_area(agent, nx, ny)
            score += new_area_revealed * 3
            
            # 4. AVOID DEAD ENDS
            future_moves = self._count_valid_moves(agent, nx, ny)
            score += future_moves * 10
            
            # 5. TOWARD SECTOR CENTER (if revisiting cells)
            if new_pos in self.visited_cells:
                sector = self._get_sector(current_pos)
                center_x = sector[0] * self.sector_size + self.sector_size // 2
                center_y = sector[1] * self.sector_size + self.sector_size // 2
                dist_to_center = abs(center_x - nx) + abs(center_y - ny)
                score -= dist_to_center // 2
            
            # 6. AVOID CYCLES
            if new_pos in self.recent_positions:
                score -= 25
            
            if score > best_score:
                best_score = score
                best_move = (dx, dy)
        
        # Update tracking
        self.visited_cells[current_pos] = self.visited_cells.get(current_pos, 0) + 1
        self.direction_history.append(best_move)
        
        return best_move
    
    def _find_immediate_target(self, agent):
        """Find targets within 3 steps"""
        x, y = int(agent.x), int(agent.y)
        
        # Check immediate neighbors (distance 1)
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 2:
                    self.target_memory[(nx, ny)] = self.steps
                    return (dx, dy)
        
        # Check distance 2
        for dx, dy in [(0, -2), (2, 0), (0, 2), (-2, 0), 
                      (1, -1), (1, 1), (-1, 1), (-1, -1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 2:
                    self.target_memory[(nx, ny)] = self.steps
                    # Move toward it (one step at a time)
                    return self._move_toward_target(agent, (nx, ny))
        
        return (0, 0)
    
    def _detect_and_enter_room(self, agent, current_pos):
        """Detect room entrances and enter them"""
        x, y = current_pos
        
        # Look for open spaces that might be rooms
        for radius in range(3, 8):
            open_cells = 0
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < agent.width and 0 <= ny < agent.height:
                        if agent.belief_map[ny, nx] == 0 or agent.belief_map[ny, nx] == -1:
                            open_cells += 1
            
            # If we found a significant open area, explore it
            if open_cells > (radius * 2) ** 2 * 0.6:  # 60% open
                # Find the nearest entrance to this open area
                for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0),
                              (1, -1), (1, 1), (-1, 1), (-1, -1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < agent.width and 0 <= ny < agent.height:
                        if agent.belief_map[ny, nx] != 1:  # Not a wall
                            return (dx, dy)
        
        return (0, 0)
    
    def _move_toward_target(self, agent, target):
        """Move toward a target position with obstacle avoidance"""
        tx, ty = target
        x, y = int(agent.x), int(agent.y)
        
        # Simple A* like approach
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        
        # Score moves by distance to target
        best_move = (0, 0)
        best_dist = float('inf')
        
        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            if self._is_valid_move(agent, nx, ny):
                dist = abs(tx - nx) + abs(ty - ny)
                if dist < best_dist:
                    best_dist = dist
                    best_move = (dx, dy)
        
        return best_move
    
    def _move_toward_with_obstacle_avoidance(self, agent, target):
        """Move toward target with smarter obstacle avoidance"""
        tx, ty = target
        x, y = int(agent.x), int(agent.y)
        
        # If we can see a clear path, use direct movement
        if self._has_clear_path(agent, x, y, tx, ty):
            return self._move_toward_target(agent, target)
        
        # Otherwise, use wall following toward target
        return self._wall_follow_toward_target(agent, target)
    
    def _wall_follow_toward_target(self, agent, target):
        """Wall follow while generally moving toward target"""
        x, y = int(agent.x), int(agent.y)
        tx, ty = target
        
        # Get all valid moves
        valid_moves = []
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self._is_valid_move(agent, nx, ny):
                valid_moves.append((dx, dy, nx, ny))
        
        if not valid_moves:
            return (0, 0)
        
        # Score moves: distance to target + wall following bonus
        best_score = -float('inf')
        best_move = valid_moves[0][:2]
        
        for dx, dy, nx, ny in valid_moves:
            score = 0
            
            # Distance to target (negative because closer is better)
            dist = abs(tx - nx) + abs(ty - ny)
            score -= dist
            
            # Wall following: prefer moves that keep a wall on right
            if self._has_wall_on_right(agent, nx, ny, dx, dy):
                score += 20
            
            # Avoid recently visited
            if (nx, ny) in self.recent_positions:
                score -= 15
            
            if score > best_score:
                best_score = score
                best_move = (dx, dy)
        
        return best_move
    
    def _has_wall_on_right(self, agent, x, y, dx, dy):
        """Check if there's a wall on the right relative to movement direction"""
        # Determine right direction based on current move
        if (dx, dy) == (0, -1):  # Moving up, right is (1, 0)
            rx, ry = 1, 0
        elif (dx, dy) == (1, 0):  # Moving right, right is (0, 1)
            rx, ry = 0, 1
        elif (dx, dy) == (0, 1):  # Moving down, right is (-1, 0)
            rx, ry = -1, 0
        else:  # Moving left, right is (0, -1)
            rx, ry = 0, -1
        
        nx, ny = x + rx, y + ry
        if 0 <= nx < agent.width and 0 <= ny < agent.height:
            return agent.belief_map[ny, nx] == 1
        
        return False
    
    def _get_sector(self, pos):
        """Convert position to sector coordinates"""
        x, y = pos
        return (x // self.sector_size, y // self.sector_size)
    
    def _find_nearest_unexplored_sector(self, current_sector):
        """Find the nearest sector that hasn't been visited"""
        # Initialize unexplored sectors if empty
        if not hasattr(self, 'sector_map_initialized'):
            self._initialize_sector_map()
            self.sector_map_initialized = True
        
        if not self.unexplored_sectors:
            return None
        
        # Find nearest unexplored sector
        nearest = None
        min_dist = float('inf')
        
        for sector in self.unexplored_sectors:
            dist = abs(sector[0] - current_sector[0]) + abs(sector[1] - current_sector[1])
            if dist < min_dist:
                min_dist = dist
                nearest = sector
        
        return nearest
    
    def _initialize_sector_map(self):
        """Initialize all sectors as unexplored"""
        # Assuming 100x100 map with sector_size=10: 10x10 sectors
        for sx in range(10):
            for sy in range(10):
                self.unexplored_sectors.add((sx, sy))
    
    def _count_new_area(self, agent, x, y):
        """Count how many unknown cells are visible from position"""
        count = 0
        # Check 5x5 area
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        count += 1
        return count
    
    def _count_valid_moves(self, agent, x, y):
        """Count how many valid moves from a position"""
        count = 0
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if self._is_valid_move(agent, nx, ny):
                count += 1
        return count
    
    def _is_valid_move(self, agent, x, y):
        """Check if move is valid"""
        return (0 <= x < agent.width and 
                0 <= y < agent.height and 
                agent.belief_map[y, x] != 1)
    
    def _has_clear_path(self, agent, x1, y1, x2, y2, max_check=20):
        """Check if there's a clear path between two points"""
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))
        
        if steps > max_check:
            return False
        
        for i in range(1, steps + 1):
            nx = x1 + (dx * i) // steps
            ny = y1 + (dy * i) // steps
            if not self._is_valid_move(agent, nx, ny):
                return False
        
        return True