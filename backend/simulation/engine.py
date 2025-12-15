class Simulation:
    def __init__(self, world, policy, max_steps=500):
        self.world = world
        self.policy = policy
        self.max_steps = max_steps
        # Create agent at (0,0)
        from simulation.agent import Agent
        self.agent = Agent(0, 0, world.width, world.height)
        
    def run(self):
        history = []
        
        # Initial sense
        self.agent.sense(self.world)
        history.append(self.agent.get_state())
        
        steps = 0
        success = False
        
        while steps < self.max_steps:
            # Check completion (found all targets)
            if len(self.agent.found_targets) == len(self.world.targets):
                success = True
                break
                
            # Decision
            dx, dy = self.policy.select_action(self.agent)
            
            # Act
            moved = self.agent.move(dx, dy, self.world)
            if not moved and (dx != 0 or dy != 0):
                # Bumped into wall or boundary, stay put but maybe update internal state if policy needs it
                pass
                
            # Sense
            self.agent.sense(self.world)
            
            # Record
            state = self.agent.get_state()
            state['step'] = steps + 1
            history.append(state)
            
            steps += 1
            
        # extensive metrics calculation
        total_cells = self.world.width * self.world.height
        
        # Coverage: cells in belief map that are NOT -1 (unknown)
        belief = self.agent.belief_map
        known_cells = 0
        for r in range(self.world.height):
            for c in range(self.world.width):
                if belief[r][c] != -1:
                    known_cells += 1
        coverage_percent = (known_cells / total_cells) * 100
        
        # Obstacle Density (Ground Truth)
        import numpy as np
        obstacles = np.count_nonzero(self.world.grid == 1)
        obstacle_density = (obstacles / total_cells) * 100
        
        # Unique cells visited (path length redundancy check)
        unique_visited = len(set([(s['x'], s['y']) for s in history]))
            
        return {
            'stats': {
                'success': success,
                'steps': steps,
                'targets_total': len(self.world.targets),
                'targets_found': len(self.agent.found_targets),
                'coverage_percent': round(coverage_percent, 2),
                'obstacle_density': round(obstacle_density, 2),
                'unique_visited': unique_visited,
                'map_width': self.world.width,
                'map_height': self.world.height
            },
            'history': history,
            'config': {
                'width': self.world.width,
                'height': self.world.height,
                'policy': self.policy.__class__.__name__,
                'seed': self.world.seed
            }
        }
