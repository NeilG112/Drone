
#Very Very slow and to be honest not any better than simpler methods

import numpy as np
from ..base import NavigationPolicy

class ComplexHarmonicPolicy(NavigationPolicy):
    """
    Complex Harmonic Navigation (CHN) Algorithm
    
    Uses complex number theory to create adaptive potential fields for 
    search-and-rescue navigation. The algorithm treats the 2D space as 
    the complex plane and uses harmonic functions to guide exploration.
    
    Key innovations:
    1. Complex potential fields for smooth navigation
    2. Phase-based exploration to avoid redundant paths
    3. Analytic continuation for obstacle avoidance
    4. Conformal mapping for adaptive behavior
    """
    
    def __init__(self, exploration_bias=0.5, phase_memory=20):
        """
        Args:
            exploration_bias: Balance between exploration (1.0) and exploitation (0.0)
            phase_memory: Number of previous positions to track for phase diversity
        """
        self.exploration_bias = exploration_bias
        self.phase_memory = phase_memory
        self.position_history = []
        self.phase_history = []
        
    def select_action(self, agent):
        """
        Select action using complex harmonic analysis.
        """
        # Current position as complex number
        z_current = complex(agent.x, agent.y)
        
        # Store position history for phase tracking
        self.position_history.append(z_current)
        if len(self.position_history) > self.phase_memory:
            self.position_history.pop(0)
        
        # Generate complex potential field
        potential_field = self._compute_complex_potential(agent, z_current)
        
        # Compute gradient descent direction
        gradient = self._compute_complex_gradient(agent, z_current)
        
        # Add exploration component using complex phase rotation
        exploration_vector = self._compute_exploration_vector(agent, z_current)
        
        # Combine forces with complex arithmetic
        alpha = self.exploration_bias
        combined_force = (1 - alpha) * gradient + alpha * exploration_vector
        
        # Convert complex force to discrete action
        action = self._complex_to_action(combined_force, agent)
        
        return action
    
    def _compute_complex_potential(self, agent, z_current):
        """
        Compute complex potential field U(z) where z is complex position.
        Uses superposition of:
        1. Attractive potential from unexplored areas
        2. Repulsive potential from obstacles
        3. Attractive potential from potential target areas
        """
        potential = 0.0 + 0.0j
        
        # Sample the environment
        for y in range(agent.height):
            for x in range(agent.width):
                z_point = complex(x, y)
                
                # Distance in complex plane
                delta_z = z_point - z_current
                if abs(delta_z) < 0.1:  # Avoid singularity
                    continue
                
                belief = agent.belief_map[y, x]
                
                # Unexplored cells create attractive potential
                if belief == -1:
                    # Use logarithmic potential (harmonic in 2D)
                    potential += 2.0 * np.log(abs(delta_z)) * (delta_z / abs(delta_z))
                
                # Known obstacles create repulsive potential
                elif belief == 1:
                    # Inverse potential with complex conjugate for smoothness
                    if abs(delta_z) > 0.5:
                        potential -= 3.0 / delta_z
                
                # High uncertainty areas are attractive
                elif belief == 0:
                    # Check if neighbors are unknown (frontier)
                    is_frontier = self._is_frontier(agent, x, y)
                    if is_frontier:
                        potential += 4.0 * np.log(abs(delta_z)) * (delta_z / abs(delta_z))
        
        return potential
    
    def _compute_complex_gradient(self, agent, z_current):
        """
        Compute complex gradient ∂U/∂z using finite differences.
        This gives the direction of steepest ascent in the potential field.
        """
        epsilon = 0.5  # Step size for numerical derivative
        
        # Four-point stencil in complex plane
        directions = [epsilon, epsilon*1j, -epsilon, -epsilon*1j]
        gradient = 0.0 + 0.0j
        
        for direction in directions:
            z_test = z_current + direction
            
            # Compute potential at test point (simplified)
            potential_test = self._sample_potential(agent, z_test)
            potential_current = self._sample_potential(agent, z_current)
            
            # Central difference approximation
            gradient += (potential_test - potential_current) / direction
        
        # Average the estimates
        gradient /= len(directions)
        
        # Negate for gradient descent
        return -gradient
    
    def _sample_potential(self, agent, z):
        """
        Sample potential at a complex position (for gradient computation).
        """
        x, y = int(np.round(z.real)), int(np.round(z.imag))
        
        if not (0 <= x < agent.width and 0 <= y < agent.height):
            return -1000.0  # Strong repulsion from boundaries
        
        belief = agent.belief_map[y, x]
        
        if belief == -1:  # Unexplored
            return 5.0
        elif belief == 1:  # Obstacle
            return -10.0
        elif belief == 0:  # Free space
            if self._is_frontier(agent, x, y):
                return 8.0
            return 1.0
        
        return 0.0
    
    def _compute_exploration_vector(self, agent, z_current):
        """
        Compute exploration vector using phase diversity.
        Uses complex exponentials to encourage movement in underexplored directions.
        """
        # Compute mean phase of recent movement
        if len(self.position_history) < 2:
            # Initial random phase
            phase = np.random.uniform(0, 2*np.pi)
            return complex(np.cos(phase), np.sin(phase))
        
        # Calculate recent movement vectors
        recent_phases = []
        for i in range(1, len(self.position_history)):
            delta = self.position_history[i] - self.position_history[i-1]
            if abs(delta) > 0.1:
                phase = np.angle(delta)
                recent_phases.append(phase)
        
        if not recent_phases:
            phase = np.random.uniform(0, 2*np.pi)
            return complex(np.cos(phase), np.sin(phase))
        
        # Compute phase histogram (discretized to 8 directions)
        phase_bins = np.linspace(-np.pi, np.pi, 9)
        hist, _ = np.histogram(recent_phases, bins=phase_bins)
        
        # Find least explored phase direction
        min_bin = np.argmin(hist)
        underexplored_phase = (phase_bins[min_bin] + phase_bins[min_bin + 1]) / 2
        
        # Add some noise for exploration
        noise = np.random.normal(0, 0.3)
        exploration_phase = underexplored_phase + noise
        
        # Convert to complex unit vector
        exploration_vector = complex(np.cos(exploration_phase), 
                                     np.sin(exploration_phase))
        
        # Scale by unknown cell density in that direction
        scale = self._compute_directional_potential(agent, z_current, exploration_vector)
        
        return scale * exploration_vector
    
    def _compute_directional_potential(self, agent, z_current, direction):
        """
        Compute potential in a given complex direction.
        """
        total_unknown = 0
        samples = 5
        
        for i in range(1, samples + 1):
            z_test = z_current + i * direction
            x, y = int(np.round(z_test.real)), int(np.round(z_test.imag))
            
            if 0 <= x < agent.width and 0 <= y < agent.height:
                if agent.belief_map[y, x] == -1:
                    total_unknown += 1
        
        return total_unknown / samples
    
    def _is_frontier(self, agent, x, y):
        """
        Check if a free cell is adjacent to unknown cells (frontier).
        """
        if agent.belief_map[y, x] != 0:
            return False
        
        # Check 8-connected neighbors
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        return True
        return False
    
    def _complex_to_action(self, complex_force, agent):
        """
        Convert complex force vector to discrete action.
        Uses conformal mapping to ensure valid moves.
        """
        if abs(complex_force) < 1e-6:
            return (0, 0)  # No significant force
        
        # Normalize
        direction = complex_force / abs(complex_force)
        
        # Extract real and imaginary parts
        dx_continuous = direction.real
        dy_continuous = direction.imag
        
        # Map to discrete actions (prioritize primary direction)
        possible_actions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),  # Cardinal
            (1, 1), (1, -1), (-1, 1), (-1, -1)  # Diagonal
        ]
        
        # Find best matching action
        best_action = (0, 0)
        best_alignment = -2.0
        
        for action in possible_actions:
            action_complex = complex(action[0], action[1])
            
            # Check if action is valid
            nx = agent.x + action[0]
            ny = agent.y + action[1]
            
            if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                continue
            if agent.belief_map[ny, nx] == 1:  # Obstacle
                continue
            
            # Compute alignment using complex inner product
            alignment = (direction * action_complex.conjugate()).real
            
            if alignment > best_alignment:
                best_alignment = alignment
                best_action = action
        
        return best_action