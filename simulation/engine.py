import numpy as np

class Simulation:
    def __init__(self, world, policy, max_steps=1000, num_drones=1):
        self.world = world
        self.policy = policy
        self.max_steps = max_steps
        self.num_drones = num_drones
        
        from simulation.agent import Agent
        
        # Create shared belief map and found targets list for multi-drone coordination
        self.shared_belief_map = np.full((world.height, world.width), -1, dtype=int)
        self.shared_found_targets = []
        
        # Mark start position as free in shared belief map
        start_x, start_y = world.start_pos
        self.shared_belief_map[start_y, start_x] = 0
        
        # Shared list of positions for coordination (mutable dicts)
        self.shared_positions = [{'x': start_x, 'y': start_y} for _ in range(num_drones)]
        
        # Create all agents at the same start position with shared state
        self.agents = []
        for i in range(num_drones):
            agent = Agent(
                start_x, start_y,
                world.width, world.height,
                agent_id=i,
                shared_belief_map=self.shared_belief_map,
                shared_found_targets=self.shared_found_targets
            )
            agent.shared_positions = self.shared_positions  # Link shared positions
            self.agents.append(agent)
        
        # Keep reference to first agent for backward compatibility
        self.agent = self.agents[0] if self.agents else None
        
    def run(self):
        history = []
        
        # Initial belief state for diffing
        prev_belief = np.full((self.world.height, self.world.width), -1, dtype=int)
        
        # Initial sense for all agents
        for agent in self.agents:
            agent.sense(self.world)
        
        # Record Initial State (Compressed)
        curr_belief = self.shared_belief_map
        rows, cols = np.where(curr_belief != prev_belief)
        diff = [[int(r), int(c), int(curr_belief[r, c])] for r, c in zip(rows, cols)]
        prev_belief = curr_belief.copy()
        
        # Build positions list for all drones
        positions = [{'x': int(agent.x), 'y': int(agent.y)} for agent in self.agents]
        
        state = {
            'x': int(self.agents[0].x),  # Backward compatibility
            'y': int(self.agents[0].y),  # Backward compatibility
            'positions': positions,  # All drone positions
            'belief_diff': diff,
            'found_targets': [(int(x), int(y)) for x, y in self.shared_found_targets],
            'step': 0
        }
        history.append(state)
        
        steps = 0
        success = False
        
        # Per-agent metrics tracking
        collisions = [0] * self.num_drones
        turns = [0] * self.num_drones
        last_directions = [(0, 0)] * self.num_drones
        
        while steps < self.max_steps:
            # Check completion (found all targets)
            if len(self.shared_found_targets) == len(self.world.targets):
                success = True
                break
            
            # Each agent takes an action
            for i, agent in enumerate(self.agents):
                # Decision
                dx, dy = self.policy.select_action(agent)
                
                # Track Turns
                last_dx, last_dy = last_directions[i]
                if (dx != last_dx or dy != last_dy) and steps > 0:
                    turns[i] += 1
                last_directions[i] = (dx, dy)
                
                # Act
                moved = agent.move(dx, dy, self.world)
                
                # Update shared positions immediately so subsequent agents see it
                self.shared_positions[i]['x'] = int(agent.x)
                self.shared_positions[i]['y'] = int(agent.y)
                
                if not moved and (dx != 0 or dy != 0):
                    # Bumped into wall or boundary
                    collisions[i] += 1
                    
                # Sense
                agent.sense(self.world)
            
            # Record (Compressed) - after all agents have acted
            curr_belief = self.shared_belief_map
            rows, cols = np.where(curr_belief != prev_belief)
            diff = [[int(r), int(c), int(curr_belief[r, c])] for r, c in zip(rows, cols)]
            prev_belief = curr_belief.copy()
            
            # Build positions list for all drones
            positions = [{'x': int(agent.x), 'y': int(agent.y)} for agent in self.agents]
            
            state = {
                'x': int(self.agents[0].x),  # Backward compatibility
                'y': int(self.agents[0].y),  # Backward compatibility
                'positions': positions,  # All drone positions
                'belief_diff': diff,
                'found_targets': [(int(x), int(y)) for x, y in self.shared_found_targets],
                'step': steps + 1
            }
            history.append(state)
            
            steps += 1
            
        # Extensive metrics calculation
        total_cells = self.world.width * self.world.height
        
        # Coverage: cells in belief map that are NOT -1 (unknown) - OPTIMIZED
        belief = self.shared_belief_map
        known_cells = np.count_nonzero(belief != -1)
        coverage_percent = (known_cells / total_cells) * 100
        
        # Obstacle Density (Ground Truth)
        obstacles = np.count_nonzero(self.world.grid == 1)
        obstacle_density = (obstacles / total_cells) * 100
        
        # Unique cells visited (combine all agent paths)
        all_visited = set()
        for agent in self.agents:
            all_visited.update(agent.path)
        unique_visited = len(all_visited)
        
        # Total steps across all agents
        total_agent_steps = sum(len(agent.path) for agent in self.agents)
        
        # Search Efficiency: Unique Visited / Total Steps (Higher is better, max 1.0)
        efficiency = (unique_visited / total_agent_steps) if total_agent_steps > 0 else 0
        
        # Aggregate metrics across all drones
        total_collisions = sum(collisions)
        total_turns = sum(turns)
            
        return {
            'stats': {
                'success': success,
                'steps': steps,
                'targets_total': len(self.world.targets),
                'targets_found': len(self.shared_found_targets),
                'coverage_percent': round(coverage_percent, 2),
                'obstacle_density': round(obstacle_density, 2),
                'unique_visited': unique_visited,
                'efficiency': round(efficiency, 3),
                'turns': total_turns,
                'collisions': total_collisions,
                'map_width': self.world.width,
                'map_height': self.world.height,
                'num_drones': self.num_drones
            },
            'history': history,
            'config': {
                'width': self.world.width,
                'height': self.world.height,
                'policy': self.policy.__class__.__name__,
                'seed': self.world.seed,
                'num_drones': self.num_drones
            }
        }
