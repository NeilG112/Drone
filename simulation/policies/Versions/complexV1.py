import numpy as np
from collections import deque
from ..base import NavigationPolicy

class ComplexPolicyV1(NavigationPolicy):
    """
    Frontier-based exploration enhanced with:
    - Complex-valued information potential field
    - Temporal memory via visit-count repulsion  
    - Gradient commitment for corridor navigation
    - Stagnation detection with Lévy-flight escape
    
    Mathematical Framework:
    - Positions z = x + iy in complex plane
    - Information potential Φ(z) with frontier attraction, obstacle repulsion, memory repulsion
    - Complex gradient ∇_C Φ guides motion via arg(∇_C Φ)
    - Commitment ratio κ triggers multi-step directional lock
    - Global progress metric η detects stagnation
    - Lévy flight restores ergodicity when stuck
    """
    
    def __init__(self, 
                 # Potential field weights
                 alpha_frontier=3.0,      # Frontier attraction strength
                 beta_obstacle=2.0,       # Obstacle repulsion strength  
                 lambda_memory=1.5,       # Memory repulsion strength
                 
                 # Kernel parameters
                 p_attract=1.5,           # Frontier attraction decay power
                 q_repel=2.0,             # Obstacle repulsion decay power
                 
                 # Radii
                 radius_local=5,          # Local computation radius
                 radius_info=10,          # Information aggregation radius
                 radius_frontier=20,      # Frontier sensing radius
                 
                 # Commitment parameters  
                 kappa_threshold=2.0,     # Commitment activation threshold
                 mu_inertia=0.3,          # Inertial bias weight
                 commit_steps=8,          # Steps to commit when κ > threshold
                 
                 # Stagnation detection
                 window_size=50,          # Progress measurement window
                 eta_min=0.05,            # Minimum acceptable progress rate
                 sigma_min=2.0,           # Minimum visit variance
                 alpha_ema=0.3,           # EMA smoothing factor
                 
                 # Lévy flight parameters
                 levy_mu=1.5,             # Lévy exponent ∈ (1, 2)
                 levy_min_length=5,       # Minimum flight length
                 levy_max_length=30,      # Maximum flight length
                 reset_radius=8,          # Visit count reset radius after escape
                 
                 epsilon=1e-6):           # Numerical stability
        
        # Store all parameters
        self.alpha_frontier = alpha_frontier
        self.beta_obstacle = beta_obstacle
        self.lambda_memory = lambda_memory
        self.p_attract = p_attract
        self.q_repel = q_repel
        self.radius_local = radius_local
        self.radius_info = radius_info
        self.radius_frontier = radius_frontier
        self.kappa_threshold = kappa_threshold
        self.mu_inertia = mu_inertia
        self.commit_steps = commit_steps
        self.window_size = window_size
        self.eta_min = eta_min
        self.sigma_min = sigma_min
        self.alpha_ema = alpha_ema
        self.levy_mu = levy_mu
        self.levy_min_length = levy_min_length
        self.levy_max_length = levy_max_length
        self.reset_radius = reset_radius
        self.epsilon = epsilon
        
        # State variables
        self.visit_counts = None          # Visit frequency map
        self.v_prev = complex(0, 0)       # Previous action (inertia)
        self.commitment_active = False    # Commitment mode flag
        self.commitment_direction = None  # Locked direction during commitment
        self.commitment_remaining = 0     # Steps remaining in commitment
        self.escape_active = False        # Lévy flight mode flag
        self.escape_direction = None      # Lévy flight direction
        self.escape_remaining = 0         # Lévy flight steps remaining
        
        # Progress tracking
        self.exploration_history = deque(maxlen=window_size)
        self.eta_smooth = None            # Smoothed progress rate
        self.total_steps = 0
        self.cells_explored_history = []
        
    def _initialize_state(self, agent):
        """Initialize state variables on first call."""
        if self.visit_counts is None:
            self.visit_counts = np.zeros((agent.height, agent.width), dtype=np.float32)
            self.eta_smooth = 1.0  # Start optimistic
    
    def _get_frontiers(self, agent):
        """
        Identify frontier cells: free cells adjacent to unknown cells.
        
        Returns:
            list of complex: Frontier positions as z = x + iy
        """
        frontiers = []
        for y in range(agent.height):
            for x in range(agent.width):
                if agent.belief_map[y, x] != 0:  # Not free
                    continue
                
                # Check if adjacent to unknown
                for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < agent.height and 0 <= nx < agent.width:
                        if agent.belief_map[ny, nx] == -1:  # Unknown
                            frontiers.append(complex(x, y))
                            break
        return frontiers
    
    def _compute_information_weight(self, agent, z_f):
        """
        Compute information weight w_f for frontier cell z_f.
        
        w_f = (N_unknown / N_total) · (1 + H_local)
        
        where:
        - N_unknown = count of unknown cells in radius R_info
        - H_local = local entropy measure
        """
        x_f, y_f = int(z_f.real), int(z_f.imag)
        
        # Count unknown cells in neighborhood
        n_unknown = 0
        n_total = 0
        entropy_sum = 0.0
        
        for dy in range(-self.radius_info, self.radius_info + 1):
            for dx in range(-self.radius_info, self.radius_info + 1):
                nx, ny = x_f + dx, y_f + dy
                if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                    continue
                
                dist = np.sqrt(dx**2 + dy**2)
                if dist > self.radius_info:
                    continue
                
                n_total += 1
                cell_val = agent.belief_map[ny, nx]
                
                if cell_val == -1:
                    n_unknown += 1
                
                # Local entropy: uncertainty in belief
                if cell_val == -1:
                    p = 0.5  # Maximum uncertainty
                else:
                    p = 0.01  # Low uncertainty
                
                if p > 0 and p < 1:
                    entropy_sum += -p * np.log2(p) - (1-p) * np.log2(1-p)
        
        # Normalize
        unknown_ratio = n_unknown / max(n_total, 1)
        h_local = entropy_sum / max(n_total, 1)
        
        w_f = unknown_ratio * (1.0 + h_local)
        return w_f
    
    def _compute_frontier_potential(self, agent, z_agent, frontiers):
        """
        Compute Φ_frontier(z) = Σ w_f · K_attract(|z - z_f|)
        Returns complex gradient ∇_C Φ_frontier.
        """
        grad = complex(0, 0)
        
        for z_f in frontiers:
            # Distance
            diff = z_f - z_agent
            dist = abs(diff)
            
            # Skip if too far
            if dist > self.radius_frontier:
                continue
            
            if dist < self.epsilon:
                continue
            
            # Information weight
            w_f = self._compute_information_weight(agent, z_f)
            
            # Gradient contribution: w_f · p · (z_f - z) / |z_f - z|^(p+1)
            # (derivative of 1/r^p potential)
            force_mag = w_f * self.p_attract / (dist ** (self.p_attract + 1) + self.epsilon)
            direction = diff / (dist + self.epsilon)
            
            grad += force_mag * direction
        
        return grad
    
    def _compute_obstacle_potential(self, agent, z_agent):
        """
        Compute Φ_obstacle gradient: repulsion from obstacles.
        """
        grad = complex(0, 0)
        
        x_a, y_a = int(z_agent.real), int(z_agent.imag)
        
        for dy in range(-self.radius_local, self.radius_local + 1):
            for dx in range(-self.radius_local, self.radius_local + 1):
                nx, ny = x_a + dx, y_a + dy
                
                if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                    continue
                
                if agent.belief_map[ny, nx] != 1:  # Not obstacle
                    continue
                
                z_o = complex(nx, ny)
                diff = z_o - z_agent
                dist = abs(diff)
                
                if dist < self.epsilon:
                    continue
                
                # Repulsion: -β · q · (z_o - z) / |z_o - z|^(q+1)
                force_mag = -self.beta_obstacle * self.q_repel / (dist ** (self.q_repel + 1) + self.epsilon)
                direction = diff / (dist + self.epsilon)
                
                grad += force_mag * direction
        
        return grad
    
    def _compute_memory_potential(self, agent, z_agent):
        """
        Compute Φ_memory gradient: repulsion from visited cells.
        """
        grad = complex(0, 0)
        
        x_a, y_a = int(z_agent.real), int(z_agent.imag)
        
        for dy in range(-self.radius_local, self.radius_local + 1):
            for dx in range(-self.radius_local, self.radius_local + 1):
                nx, ny = x_a + dx, y_a + dy
                
                if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                    continue
                
                visit_count = self.visit_counts[ny, nx]
                
                if visit_count < 0.1:  # Skip unvisited
                    continue
                
                z_v = complex(nx, ny)
                diff = z_v - z_agent
                dist = abs(diff)
                
                if dist < self.epsilon:
                    continue
                
                # Repulsion: -λ · V(z_v) / |z_v - z|^2
                force_mag = -self.lambda_memory * visit_count / (dist**2 + self.epsilon)
                direction = diff / (dist + self.epsilon)
                
                grad += force_mag * direction
        
        return grad
    
    def _compute_commitment_ratio(self, grad_frontier, grad_memory):
        """
        Compute κ = |∇Φ_frontier| / (|∇Φ_memory| + ε)
        """
        mag_frontier = abs(grad_frontier)
        mag_memory = abs(grad_memory)
        
        kappa = mag_frontier / (mag_memory + self.epsilon)
        return kappa
    
    def _update_progress_metric(self, agent):
        """
        Update exploration progress metric η(t).
        """
        cells_explored = np.sum(agent.belief_map != -1)
        self.cells_explored_history.append(cells_explored)
        
        # Compute recent progress
        if len(self.cells_explored_history) >= self.window_size:
            old_count = self.cells_explored_history[-self.window_size]
            eta_current = (cells_explored - old_count) / self.window_size
        else:
            eta_current = cells_explored / (self.total_steps + 1)
        
        # Exponential moving average
        if self.eta_smooth is None:
            self.eta_smooth = eta_current
        else:
            self.eta_smooth = self.alpha_ema * eta_current + (1 - self.alpha_ema) * self.eta_smooth
    
    def _detect_stagnation(self, agent):
        """
        Detect if exploration is stagnating.
        
        Returns True if:
        - Progress rate η < η_min
        - Visit variance < σ_min (spatial concentration)
        """
        if self.eta_smooth < self.eta_min:
            # Check visit variance
            recent_visits = []
            x_a, y_a = agent.x, agent.y
            for dy in range(-10, 11):
                for dx in range(-10, 11):
                    nx, ny = x_a + dx, y_a + dy
                    if 0 <= nx < agent.width and 0 <= ny < agent.height:
                        recent_visits.append(self.visit_counts[ny, nx])
            
            if len(recent_visits) > 0:
                visit_var = np.var(recent_visits)
                if visit_var < self.sigma_min:
                    return True
        
        return False
    
    def _sample_levy_flight(self):
        """
        Sample Lévy flight length L ~ L^(-μ).
        """
        # Inverse transform sampling for power law
        u = np.random.uniform(0, 1)
        L_min = self.levy_min_length
        L_max = self.levy_max_length
        
        # L ~ U^(1/(1-μ)) for truncated power law
        if self.levy_mu == 1.0:
            L = L_min * np.exp(u * np.log(L_max / L_min))
        else:
            exponent = 1.0 / (1.0 - self.levy_mu)
            L = (L_min**(1-self.levy_mu) + u * (L_max**(1-self.levy_mu) - L_min**(1-self.levy_mu))) ** exponent
        
        return int(np.clip(L, L_min, L_max))
    
    def _initiate_levy_escape(self, agent):
        """
        Initiate Lévy flight escape maneuver.
        """
        self.escape_active = True
        self.escape_remaining = self._sample_levy_flight()
        
        # Random direction
        theta = np.random.uniform(0, 2 * np.pi)
        self.escape_direction = complex(np.cos(theta), np.sin(theta))
        
        # Reset visit counts in local region to allow revisits
        x_a, y_a = agent.x, agent.y
        for dy in range(-self.reset_radius, self.reset_radius + 1):
            for dx in range(-self.reset_radius, self.reset_radius + 1):
                nx, ny = x_a + dx, y_a + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    dist = np.sqrt(dx**2 + dy**2)
                    if dist <= self.reset_radius:
                        self.visit_counts[ny, nx] *= 0.5  # Partial reset
    
    def select_action(self, agent):
        """
        Select action using complex information field with stochastic escape.
        """
        self._initialize_state(agent)
        self.total_steps += 1
        
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # Up, Right, Down, Left
        z_agent = complex(agent.x, agent.y)
        
        # Update progress tracking
        self._update_progress_metric(agent)
        
        # Check for stagnation
        if not self.escape_active and not self.commitment_active:
            if self._detect_stagnation(agent):
                self._initiate_levy_escape(agent)
        
        # MODE 1: Lévy Flight Escape
        if self.escape_active and self.escape_remaining > 0:
            # Follow escape direction
            grad_total = self.escape_direction
            self.escape_remaining -= 1
            
            if self.escape_remaining <= 0:
                self.escape_active = False
        
        # MODE 2: Gradient Commitment
        elif self.commitment_active and self.commitment_remaining > 0:
            # Follow locked direction
            grad_total = self.commitment_direction
            self.commitment_remaining -= 1
            
            if self.commitment_remaining <= 0:
                self.commitment_active = False
        
        # MODE 3: Normal Navigation
        else:
            # Get frontiers
            frontiers = self._get_frontiers(agent)
            
            if len(frontiers) == 0:
                # No frontiers: exploration complete or stuck
                # Default to random walk
                valid_moves = []
                for dx, dy in moves:
                    nx, ny = agent.x + dx, agent.y + dy
                    if (0 <= nx < agent.width and 0 <= ny < agent.height and 
                        agent.belief_map[ny, nx] != 1):
                        valid_moves.append((dx, dy))
                
                if valid_moves:
                    return valid_moves[np.random.randint(len(valid_moves))]
                else:
                    return (0, 0)
            
            # Compute potential gradients
            grad_frontier = self._compute_frontier_potential(agent, z_agent, frontiers)
            grad_obstacle = self._compute_obstacle_potential(agent, z_agent)
            grad_memory = self._compute_memory_potential(agent, z_agent)
            
            # Check commitment condition
            kappa = self._compute_commitment_ratio(grad_frontier, grad_memory)
            
            if kappa > self.kappa_threshold and abs(grad_frontier) > self.epsilon:
                # Enter commitment mode
                self.commitment_active = True
                self.commitment_direction = grad_frontier
                self.commitment_remaining = self.commit_steps
                grad_total = grad_frontier
            else:
                # Normal mode: combine all gradients
                grad_total = (self.alpha_frontier * grad_frontier + 
                             grad_obstacle + 
                             grad_memory)
        
        # Normalize gradient
        if abs(grad_total) < self.epsilon:
            grad_total = complex(1, 0)  # Default direction
        else:
            grad_total = grad_total / abs(grad_total)
        
        # Action selection via projection
        best_action = (0, 0)
        best_score = -np.inf
        
        for dx, dy in moves:
            nx, ny = agent.x + dx, agent.y + dy
            
            # Check validity
            if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                continue
            if agent.belief_map[ny, nx] == 1:  # Obstacle
                continue
            
            # Action as complex vector
            v_a = complex(dx, dy)
            
            # Alignment score with inertia
            score = (grad_total * v_a.conjugate()).real + self.mu_inertia * (self.v_prev * v_a.conjugate()).real
            
            if score > best_score:
                best_score = score
                best_action = (dx, dy)
        
        # Update state
        self.visit_counts[agent.y, agent.x] += 1.0
        
        if best_action != (0, 0):
            self.v_prev = complex(best_action[0], best_action[1])
        
        # Abort commitment/escape if stuck
        if best_action == (0, 0):
            self.commitment_active = False
            self.escape_active = False
        
        return best_action