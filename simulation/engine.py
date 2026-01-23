import numpy as np
import random

class Simulation:
    def __init__(self, world, policy, max_steps=1000, num_drones=1):
        self.world = world
        self.policy = policy
        self.max_steps = max_steps
        self.num_drones = num_drones
        self.comm_range = 10.0 # Default communication range (e.g. 10 cells)
        # Set to None or float('inf') for infinite range
        
        from simulation.agent import Agent
        
        # Create shared belief map and found targets list for multi-drone coordination
        self.shared_belief_map = np.full((world.height, world.width), -1, dtype=int)
        self.shared_found_targets = []  # Positions of found targets (for display)
        self.shared_found_target_ids = set()  # Indices of found targets (for tracking)
        
        # Mark start position as free in shared belief map
        start_x, start_y = world.start_pos
        self.shared_belief_map[start_y, start_x] = 0
        
        # Shared list of positions for coordination (mutable dicts)
        self.shared_positions = [{'x': start_x, 'y': start_y} for _ in range(num_drones)]
        
        # Create all agents at the same start position
        # NOTE: For "Limited Communication", agents do NOT share belief map by default.
        # We pass None for shared_belief_map so they create their own.
        self.agents = []
        for i in range(num_drones):
            agent = Agent(
                start_x, start_y,
                world.width, world.height,
                agent_id=i,
                shared_belief_map=None, # Independent belief maps
                shared_found_targets=None # Independent target lists (merge later)
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
        positions = [{'x': int(agent.x), 'y': int(agent.y), 'battery': round(agent.battery, 1), 'is_dead': agent.is_dead} for agent in self.agents]
        
        state = {
            'x': int(self.agents[0].x),  # Backward compatibility
            'y': int(self.agents[0].y),  # Backward compatibility
            'positions': positions,  # All drone positions
            'belief_diff': diff,
            'found_targets': [(int(x), int(y)) for x, y in self.shared_found_targets],
            'targets': [(int(x), int(y)) for x, y in self.world.targets],  # Current target positions
            'step': 0
        }
        history.append(state)
        
        steps = 0
        success = False
        
        # Per-agent metrics tracking
        collisions = [0] * self.num_drones
        turns = [0] * self.num_drones
        last_directions = [(0, 0)] * self.num_drones
        
        # Enhanced analytics tracking
        cells_known_prev_step = np.count_nonzero(self.shared_belief_map != -1)
        new_cells_per_step = []  # Track info gain per step
        steps_since_new_info = 0
        max_steps_without_new_info = 0
        target_found_steps = []  # Step when each target was found
        initial_energy = sum(agent.battery for agent in self.agents)
        
        # NEW: Additional analytics tracking
        communication_events = []  # Track communication connectivity per step
        frontier_sizes = []  # Track frontier size over time
        agent_distances_traveled = [0] * self.num_drones  # Track distance each agent travels
        agent_last_positions = [(agent.x, agent.y) for agent in self.agents]  # For distance calculation
        exploration_rates = []  # Track exploration rate over time
        network_partitions = []  # Track number of communication partitions per step
        auction_events = []  # Track auction-related metrics (if applicable)
        backtracking_counts = [0] * self.num_drones  # Track backtracking per agent
        idle_steps = [0] * self.num_drones  # Track steps where agent doesn't move
        
        while steps < self.max_steps:
            # Check completion - all targets found by ID
            # Found targets no longer move, so this is reliable
            if len(self.shared_found_target_ids) == len(self.world.targets):
                success = True
                break
            
            # Each agent takes an action
            for i, agent in enumerate(self.agents):
                if agent.is_dead:
                    # Skip dead agents
                    continue
                    
                # Charging Logic
                if agent.is_charging:
                    agent.charging_timer += 1
                    # Linear charge: 20 per step -> 1000 in 50 steps
                    agent.battery = min(agent.max_battery, agent.battery + (agent.max_battery / 50.0))
                    
                    if agent.charging_timer >= 50:
                        agent.is_charging = False
                        agent.charging_timer = 0
                        
                    # Skip action while charging
                    # Update pos in shared list just in case (static)
                    self.shared_positions[i]['x'] = int(agent.x)
                    self.shared_positions[i]['y'] = int(agent.y)
                    continue
                    
                # Check for Start of Charging
                # If at base and battery < max, start charging
                start_x, start_y = self.world.start_pos
                if int(agent.x) == start_x and int(agent.y) == start_y and agent.battery < agent.max_battery:
                    # Only charge if we actually need it (e.g. < 90%)
                    if agent.battery < agent.max_battery * 0.9:
                        agent.is_charging = True
                        agent.charging_timer = 0
                        continue

                # Decision

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
                
                # NEW: Track distance traveled and idle steps
                if moved:
                    # Calculate Manhattan distance moved
                    last_x, last_y = agent_last_positions[i]
                    distance = abs(agent.x - last_x) + abs(agent.y - last_y)
                    agent_distances_traveled[i] += distance
                    agent_last_positions[i] = (agent.x, agent.y)
                else:
                    if dx == 0 and dy == 0:
                        idle_steps[i] += 1
                
                # NEW: Track backtracking (revisiting cells)
                current_pos = (int(agent.x), int(agent.y))
                if len(agent.path) >= 3:  # Need at least 3 positions to detect backtracking
                    recent_positions = agent.path[-10:]  # Look at last 10 positions
                    if current_pos in recent_positions[:-1]:  # If current pos was visited recently
                        backtracking_counts[i] += 1
                
                if not moved and (dx != 0 or dy != 0) and not agent.is_dead:
                    # Bumped into wall or boundary
                    collisions[i] += 1
                    
                # Sense
                agent.sense(self.world)
            
            # Communication / Map Merging Step
            # Build connectivity graph
            adj = [[] for _ in range(self.num_drones)]
            for i in range(self.num_drones):
                for j in range(i + 1, self.num_drones):
                    if self.agents[i].is_dead or self.agents[j].is_dead:
                        # Dead agents can't talk? Or maybe they buffer? Let's say dead = radio silence.
                        continue
                        
                    # Calculate distance
                    dist = abs(self.agents[i].x - self.agents[j].x) + abs(self.agents[i].y - self.agents[j].y)
                    
                    if self.comm_range is None or dist <= self.comm_range:
                        adj[i].append(j)
                        adj[j].append(i)
            
            # Find connected components (BFS)
            visited = [False] * self.num_drones
            
            for i in range(self.num_drones):
                if not visited[i] and not self.agents[i].is_dead:
                    # Found a new component
                    component = []
                    q = [i]
                    visited[i] = True
                    while q:
                        curr = q.pop(0)
                        component.append(curr)
                        for neighbor in adj[curr]:
                            if not visited[neighbor]:
                                visited[neighbor] = True
                                q.append(neighbor)
                                
                    # Merge maps for this component
                    if len(component) > 1:
                        self._merge_component_maps([self.agents[k] for k in component])
                        
                    # Update connected_neighbors for agents in this component
                    # Each agent knows everyone else in the component?
                    # Or just direct neighbors?
                    # "Broadcast assignments" implies full connectivity or multi-hop.
                    # Let's give them the full component list (minus self) as "connected network".
                    for agent_idx in component:
                         others = [k for k in component if k != agent_idx]
                         self.agents[agent_idx].connected_neighbors = others
            
            # NEW: Track communication metrics
            # Count connected components (network partitions)
            partitions_this_step = 0
            connected_agents = 0
            visited = [False] * self.num_drones
            for i in range(self.num_drones):
                if not visited[i] and not self.agents[i].is_dead:
                    partitions_this_step += 1
                    # Count agents in this component
                    component_size = 0
                    q = [i]
                    visited[i] = True
                    while q:
                        curr = q.pop(0)
                        component_size += 1
                        for neighbor in adj[curr]:
                            if not visited[neighbor]:
                                visited[neighbor] = True
                                q.append(neighbor)
                    connected_agents += component_size
            
            network_partitions.append(partitions_this_step)
            communication_events.append({
                'partitions': partitions_this_step,
                'connected_agents': connected_agents,
                'total_alive': sum(1 for agent in self.agents if not agent.is_dead)
            })

            # Update God View (for Visualization) - Union of ALL agents knowledge
            for agent in self.agents:
                known_mask = agent.belief_map != -1
                self.shared_belief_map[known_mask] = agent.belief_map[known_mask]
                
                # Merge found target IDs (by index, not position)
                for tid in agent.found_target_ids:
                    if tid not in self.shared_found_target_ids:
                        self.shared_found_target_ids.add(tid)
            
            # Record (Compressed) - after all agents have acted
            curr_belief = self.shared_belief_map
            rows, cols = np.where(curr_belief != prev_belief)
            diff = [[int(r), int(c), int(curr_belief[r, c])] for r, c in zip(rows, cols)]
            prev_belief = curr_belief.copy()
            
            # Build positions list for all drones
            positions = [{'x': int(agent.x), 'y': int(agent.y), 'battery': round(agent.battery, 1), 'max_battery': agent.max_battery, 'is_dead': agent.is_dead} for agent in self.agents]
            
            # Build found_targets list with CURRENT positions (for moving targets)
            found_targets_current = []
            for tid in self.shared_found_target_ids:
                if tid < len(self.world.targets):
                    found_targets_current.append(self.world.targets[tid])
            
            state = {
                'x': int(self.agents[0].x),  # Backward compatibility
                'y': int(self.agents[0].y),  # Backward compatibility
                'positions': positions,  # All drone positions
                'belief_diff': diff,
                'found_targets': [(int(x), int(y)) for x, y in found_targets_current],
                'targets': [(int(x), int(y)) for x, y in self.world.targets],  # Current target positions
                'step': steps + 1
            }
            history.append(state)
            
            # Track information gain (new cells discovered this step)
            cells_known_now = np.count_nonzero(self.shared_belief_map != -1)
            new_cells = cells_known_now - cells_known_prev_step
            new_cells_per_step.append(new_cells)
            cells_known_prev_step = cells_known_now
            
            # NEW: Track frontier size (unknown cells adjacent to known free cells)
            frontier_size = self._calculate_frontier_size()
            frontier_sizes.append(frontier_size)
            
            # NEW: Track exploration rate (new_cells / frontier_size if frontier_size > 0 else 0)
            exploration_rate = (new_cells / frontier_size) if frontier_size > 0 else 0
            exploration_rates.append(exploration_rate)
            
            # Track steps without new info
            if new_cells == 0:
                steps_since_new_info += 1
                max_steps_without_new_info = max(max_steps_without_new_info, steps_since_new_info)
            else:
                steps_since_new_info = 0
            
            # Track target discovery times
            targets_found_this_step = len(self.shared_found_target_ids)
            while len(target_found_steps) < targets_found_this_step:
                target_found_steps.append(steps + 1)
            
            steps += 1
            
            # Dynamic Targets (Random Walk) - only UNFOUND targets move
            # Found targets stay in place (they've been "rescued")
            if random.random() < 0.1: # 10% chance per step for ANY movement
                # Get list of unfound target indices
                unfound_indices = [i for i in range(len(self.world.targets)) 
                                   if i not in self.shared_found_target_ids]
                if unfound_indices:
                    t_idx = random.choice(unfound_indices)
                    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
                    dx, dy = random.choice(moves)
                    self.world.move_target(t_idx, dx, dy)
        
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
        visited_counts = {} # cell -> total visit count (all agents)
        
        for agent in self.agents:
            for cell in agent.path:
                all_visited.add(cell)
                visited_counts[cell] = visited_counts.get(cell, 0) + 1
                
        unique_visited = len(all_visited)
        
        # Overlap Rate: % of visited cells that were visited by >1 agent
        # Count cells visited by multiple AGENTS (not just multiple times)
        agent_visit_sets = [set(agent.path) for agent in self.agents]
        overlapping_cells = 0
        for cell in all_visited:
            agents_who_visited = sum(1 for s in agent_visit_sets if cell in s)
            if agents_who_visited > 1:
                overlapping_cells += 1
        overlap_rate = (overlapping_cells / unique_visited * 100) if unique_visited > 0 else 0.0
        
        # Total steps across all agents
        total_agent_steps = sum(len(agent.path) for agent in self.agents)
        
        # Search Efficiency: Unique Visited / Total Steps (Higher is better, max 1.0)
        efficiency = (unique_visited / total_agent_steps) if total_agent_steps > 0 else 0
        
        # Aggregate metrics across all drones
        total_collisions = sum(collisions)
        total_turns = sum(turns)
        avg_battery = sum(agent.battery for agent in self.agents) / self.num_drones
        
        # === NEW ENHANCED ANALYTICS ===
        
        # Revisit metrics: count total revisits (visits beyond first to each cell)
        total_revisits = sum(max(0, count - 1) for count in visited_counts.values())
        max_cell_visits = max(visited_counts.values()) if visited_counts else 0
        avg_visits_per_cell = (sum(visited_counts.values()) / len(visited_counts)) if visited_counts else 0
        
        # Information gain
        avg_information_gain = (sum(new_cells_per_step) / len(new_cells_per_step)) if new_cells_per_step else 0
        
        # Movement quality (normalized rates)
        turn_rate = (total_turns / steps) if steps > 0 else 0
        collision_rate = (total_collisions / steps) if steps > 0 else 0
        
        # Target finding timing
        first_target_step = target_found_steps[0] if target_found_steps else 0
        avg_time_to_target = (sum(target_found_steps) / len(target_found_steps)) if target_found_steps else 0
        
        # Energy metrics
        total_energy_used = initial_energy - sum(agent.battery for agent in self.agents)
        targets_found = len(self.shared_found_target_ids)
        energy_per_target = (total_energy_used / targets_found) if targets_found > 0 else 0
            
        return {
            'stats': {
                'success': success,
                'steps': steps,
                'targets_total': len(self.world.targets),
                'targets_found': targets_found,
                'coverage_percent': round(coverage_percent, 2),
                'obstacle_density': round(obstacle_density, 2),
                'unique_visited': unique_visited,
                'efficiency': round(efficiency, 3),
                'turns': total_turns,
                'collisions': total_collisions,
                'avg_battery': round(avg_battery, 1),
                'overlap_rate': round(overlap_rate, 2),
                'map_width': self.world.width,
                'map_height': self.world.height,
                'num_drones': self.num_drones,
                # Enhanced analytics
                'revisits': total_revisits,
                'max_cell_visits': max_cell_visits,
                'avg_visits_per_cell': round(avg_visits_per_cell, 2),
                'avg_information_gain': round(avg_information_gain, 2),
                'max_steps_without_new_info': max_steps_without_new_info,
                'turn_rate': round(turn_rate, 3),
                'collision_rate': round(collision_rate, 3),
                'first_target_step': first_target_step,
                'avg_time_to_target': round(avg_time_to_target, 1),
                'total_energy_used': round(total_energy_used, 1),
                'energy_per_target': round(energy_per_target, 1),
                # NEW: Additional analytics metrics
                'total_distance_traveled': round(sum(agent_distances_traveled), 1),
                'avg_distance_per_agent': round(sum(agent_distances_traveled) / self.num_drones, 1),
                'total_idle_steps': sum(idle_steps),
                'avg_idle_steps_per_agent': round(sum(idle_steps) / self.num_drones, 1),
                'total_backtracking': sum(backtracking_counts),
                'avg_backtracking_per_agent': round(sum(backtracking_counts) / self.num_drones, 1),
                'avg_frontier_size': round(sum(frontier_sizes) / len(frontier_sizes), 1) if frontier_sizes else 0,
                'max_frontier_size': max(frontier_sizes) if frontier_sizes else 0,
                'avg_exploration_rate': round(sum(exploration_rates) / len(exploration_rates), 3) if exploration_rates else 0,
                'avg_network_partitions': round(sum(network_partitions) / len(network_partitions), 1) if network_partitions else 0,
                'max_network_partitions': max(network_partitions) if network_partitions else 0,
                'communication_connectivity': round(sum(ce['connected_agents'] / ce['total_alive'] if ce['total_alive'] > 0 else 0 for ce in communication_events) / len(communication_events), 3) if communication_events else 0
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

    def _calculate_frontier_size(self):
        """Calculate the number of frontier cells (unknown cells adjacent to known free cells)."""
        belief = self.shared_belief_map
        height, width = belief.shape
        frontier_count = 0
        
        for y in range(height):
            for x in range(width):
                if belief[y, x] == -1:  # Unknown cell
                    # Check if adjacent to a known free cell
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < height and 0 <= nx < width and belief[ny, nx] == 0:
                            frontier_count += 1
                            break  # Count each frontier cell only once
        
        return frontier_count

    def _merge_component_maps(self, agents_in_component):
        """Merges belief maps and target lists for a group of connected agents."""
        if not agents_in_component:
            return
            
        # 1. Create a temporary union map
        # Optimization: Pick the first agent's map as base (copy)
        union_map = agents_in_component[0].belief_map.copy()
        union_target_ids = set(agents_in_component[0].found_target_ids)
        # Union victim probs (max)
        union_victim_probs = agents_in_component[0].victim_prob_map.copy()
        
        # 2. Accumulate all others
        for agent in agents_in_component[1:]:
            # Belief Map
            known_mask = agent.belief_map != -1
            union_map[known_mask] = agent.belief_map[known_mask]
            
            # Prey/Victim Probs - Take MAX probability
            union_victim_probs = np.maximum(union_victim_probs, agent.victim_prob_map)
            
            # Targets (now tracked by IDs)
            for tid in agent.found_target_ids:
                if tid not in union_target_ids:
                    union_target_ids.add(tid)
                    
        # 3. Distribute back to all
        for agent in agents_in_component:
            # We copy back the union. 
            # Note: This overwrites local knowledge? 
            # Since union includes local knowledge, it is safe.
            # But what if there was a conflict? (Noise).
            # If Agent A thinks (0,0) is 1, and Agent B thinks (0,0) is 0.
            # The union takes last written.
            # Then both get that value. They agree.
            # This is "Last One Wins" or "Arbitrary" consensus. Good enough for now.
            
            # Optimization: Only update if different? 
            # Numpy copy is fast enough for small grids.
            agent.belief_map[:] = union_map[:]
            agent.found_target_ids = set(union_target_ids)  # Copy the set
            agent.victim_prob_map[:] = union_victim_probs[:]
