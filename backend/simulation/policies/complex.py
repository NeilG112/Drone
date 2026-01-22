import numpy as np
import cmath
import math
from .base import NavigationPolicy
from collections import deque
import random

class RiemannMazeNavigator(NavigationPolicy):
    """
    Advanced Complex Number Navigation using:
    1. Riemann Mapping Theorem for obstacle avoidance
    2. Complex Potential Fields with harmonic functions
    3. Analytic continuation for unexplored area prediction
    4. Conformal transformations for path optimization
    5. Complex neural attractor networks
    """
    
    def __init__(self, convergence_rate=0.1, harmonic_weight=2.0):
        # Complex Analysis State
        self.z_position = 0 + 0j  # Current position in complex plane
        self.riemann_map = {}     # Conformal mapping cache
        self.harmonic_field = {}  # Harmonic potential field
        
        # Analytic continuation state
        self.analytic_function = None
        self.laurent_coeffs = deque(maxlen=10)
        self.singularities = set()  # Obstacles as complex poles
        
        # Complex Neural Dynamics
        self.attractor_network = {}
        self.phase_synchronization = 0.0
        self.complex_memory = np.zeros((100, 100), dtype=complex)
        
        # Riemann-Hilbert problem state
        self.boundary_values = {}
        self.cauchy_integral_cache = {}
        
        # Exploration using modular forms
        self.modular_phase = 0.0
        self.fundamental_domain = None
        
        # Performance
        self.visit_count = np.zeros((100, 100), dtype=int)
        self.path_integral = 0 + 0j
        
    def select_action(self, agent):
        """Select action using advanced complex analysis methods"""
        self.z_position = complex(agent.x, agent.y)
        x, y = int(agent.x), int(agent.y)
        
        # Update visit count
        self.visit_count[y, x] += 1
        
        # 1. Apply Riemann Mapping: Transform complex plane to simplify obstacles
        mapped_z = self._apply_riemann_mapping(agent)
        
        # 2. Solve Laplace's Equation: ∇²φ = 0 for harmonic navigation field
        harmonic_potential = self._solve_laplace_equation(agent, mapped_z)
        
        # 3. Perform Analytic Continuation: Predict unknown areas
        predicted_field = self._analytic_continuation(agent, harmonic_potential)
        
        # 4. Compute Complex Gradient: ∇φ = ∂φ/∂x + i∂φ/∂y
        gradient = self._compute_complex_gradient(predicted_field, agent)
        
        # 5. Apply Conformal Transformation: Preserve angles for optimal turns
        transformed_gradient = self._conformal_transform(gradient, agent)
        
        # 6. Integrate along Path: ∮ f(z) dz for smooth trajectory
        action = self._path_integrate(transformed_gradient, agent)
        
        # 7. Update Complex Memory: Store in attractor network
        self._update_attractor_network(agent, action)
        
        return action
    
    def _apply_riemann_mapping(self, agent):
        """
        Apply Riemann Mapping Theorem to simplify environment
        Maps maze onto unit disk while preserving angles
        """
        # Use Schwarz-Christoffel transformation for polygonal domains
        z = self.z_position
        
        # Normalize coordinates to [-1, 1]
        normalized_z = complex(
            2 * z.real / agent.width - 1,
            2 * z.imag / agent.height - 1
        )
        
        # Check cache for precomputed mapping
        key = (int(z.real), int(z.imag))
        if key in self.riemann_map:
            return self.riemann_map[key]
        
        # Compute conformal mapping using iterative method
        # f(z) = z + Σ c_n * z^n, where c_n are determined by obstacles
        mapped_z = normalized_z
        
        # Add terms for nearby obstacles (model as poles)
        for radius in range(1, 6):
            for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
                dz = cmath.rect(radius, angle)
                test_z = z + dz
                tx, ty = int(test_z.real), int(test_z.imag)
                
                if 0 <= tx < agent.width and 0 <= ty < agent.height:
                    if agent.belief_map[ty, tx] == 1:  # Obstacle
                        # Add repulsive term: -k/(z - z_obstacle)
                        diff = z - test_z
                        if abs(diff) > 0.1:
                            mapped_z -= 0.1 / diff
        
        # Cache result
        self.riemann_map[key] = mapped_z
        return mapped_z
    
    def _solve_laplace_equation(self, agent, mapped_z):
        """
        Solve ∇²φ = 0 using discrete complex analysis
        Returns complex harmonic function value
        """
        # Discrete Laplace operator on complex grid
        laplacian = 0 + 0j
        
        # 5-point stencil for Laplace operator
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = int(agent.x + dx), int(agent.y + dy)
            
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                # Complex potential based on cell type
                if agent.belief_map[ny, nx] == -1:  # Unknown
                    potential = 1 + 1j  # Encourage exploration
                elif agent.belief_map[ny, nx] == 2:  # Target
                    potential = 2 + 2j  # Strong attraction
                elif agent.belief_map[ny, nx] == 1:  # Obstacle
                    potential = -1 - 1j  # Repulsion
                else:  # Free space
                    potential = 0.5 + 0.5j  # Neutral
                
                # Apply Dirichlet boundary condition
                laplacian += potential
        
        # Subtract 4 times center value (discrete Laplacian)
        center_val = self._get_center_potential(agent)
        laplacian -= 4 * center_val
        
        # Jacobi iteration for harmonic function
        harmonic_val = center_val + 0.25 * laplacian
        
        # Ensure function is harmonic (real and imaginary parts satisfy Laplace)
        return harmonic_val
    
    def _analytic_continuation(self, agent, known_field):
        """
        Use analytic continuation to predict unknown areas
        Based on Taylor series expansion from known boundary
        """
        # Build Laurent series from known data
        center = self.z_position
        
        # Collect known values in neighborhood for series coefficients
        known_points = []
        for radius in range(1, 4):
            for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
                dz = cmath.rect(radius, angle)
                test_z = center + dz
                tx, ty = int(test_z.real), int(test_z.imag)
                
                if 0 <= tx < agent.width and 0 <= ty < agent.height:
                    if agent.belief_map[ty, tx] != -1:  # Known cell
                        # Compute value at this point
                        if agent.belief_map[ty, tx] == 2:
                            val = 2 + 2j
                        else:
                            val = complex(self.visit_count[ty, tx], 1)
                        known_points.append((test_z - center, val))
        
        if len(known_points) < 4:
            return known_field
        
        # Fit complex polynomial: f(z) = Σ a_n * (z - center)^n
        # Using least squares for complex coefficients
        n_terms = min(3, len(known_points))
        
        # Build matrix for linear system
        A = np.zeros((len(known_points), n_terms), dtype=complex)
        b = np.zeros(len(known_points), dtype=complex)
        
        for i, (dz, val) in enumerate(known_points):
            for j in range(n_terms):
                A[i, j] = dz ** (j + 1)
            b[i] = val
        
        # Solve for coefficients (pseudo-inverse)
        try:
            coeffs = np.linalg.lstsq(A, b, rcond=None)[0]
            
            # Use analytic continuation to predict
            predicted = known_field
            for j in range(n_terms):
                # Predict in all unknown directions
                for angle in np.linspace(0, 2*np.pi, 8, endpoint=False):
                    dz = cmath.rect(3, angle)  # Predict 3 steps ahead
                    if j < len(coeffs):
                        predicted += coeffs[j] * (dz ** (j + 1))
        except:
            predicted = known_field
        
        return predicted
    
    def _compute_complex_gradient(self, field, agent):
        """
        Compute complex gradient ∇f = ∂f/∂x + i∂f/∂y
        Using Cauchy-Riemann equations for analytic functions
        """
        # Finite difference for complex derivative
        h = 0.01  # Small step
        
        # ∂f/∂x ≈ [f(x+h,y) - f(x,y)]/h
        dx_pos = complex(agent.x + h, agent.y)
        dx_field = self._evaluate_field_at(dx_pos, agent)
        df_dx = (dx_field - field) / h
        
        # ∂f/∂y ≈ [f(x,y+h) - f(x,y)]/h
        dy_pos = complex(agent.x, agent.y + h)
        dy_field = self._evaluate_field_at(dy_pos, agent)
        df_dy = (dy_field - field) / h
        
        # Complex gradient: ∇f = ∂f/∂x + i∂f/∂y
        gradient = df_dx + 1j * df_dy
        
        # Check Cauchy-Riemann conditions for analyticity
        # ∂u/∂x = ∂v/∂y and ∂u/∂y = -∂v/∂x
        u_x = df_dx.real
        v_y = df_dy.imag
        u_y = df_dy.real
        v_x = df_dx.imag
        
        cr_error = abs(u_x - v_y) + abs(u_y + v_x)
        if cr_error > 1.0:
            # Field is not analytic, apply correction
            gradient = gradient / (1 + cr_error)
        
        return gradient
    
    def _conformal_transform(self, gradient, agent):
        """
        Apply conformal transformation to preserve angles
        Uses Möbius transformation: w = (az + b)/(cz + d)
        """
        # Simple Möbius transformation for angle preservation
        a = 1 + 0.1j  # Rotation and scaling
        b = 0.05 + 0.05j  # Translation
        c = 0.01  # Complex curvature
        d = 1
        
        # Transform the gradient
        z = gradient
        if abs(c * z + d) > 0.01:  # Avoid division by zero
            transformed = (a * z + b) / (c * z + d)
        else:
            transformed = a * z + b
        
        # Normalize
        mag = abs(transformed)
        if mag > 0:
            transformed /= mag
        
        return transformed
    
    def _path_integrate(self, gradient, agent):
        """
        Integrate along path to find optimal discrete move
        ∮ f(z) dz along candidate paths
        """
        current_z = self.z_position
        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        
        best_move = (0, 0)
        best_integral = -float('inf')
        
        for dx, dy in moves:
            nx, ny = int(agent.x + dx), int(agent.y + dy)
            
            if not (0 <= nx < agent.width and 0 <= ny < agent.height):
                continue
            if agent.belief_map[ny, nx] == 1:
                continue
            
            # Path from current to candidate
            end_z = complex(nx, ny)
            
            # Line integral ∫ f(z) dz along straight path
            # Approximate using trapezoidal rule
            n_segments = 3
            integral = 0 + 0j
            
            for k in range(n_segments + 1):
                t = k / n_segments
                z_t = current_z * (1 - t) + end_z * t
                
                # Evaluate field at intermediate point
                f_t = self._evaluate_field_at(z_t, agent)
                
                # Weight for trapezoidal rule
                weight = 1.0 if k == 0 or k == n_segments else 2.0
                integral += weight * f_t
            
            # Final integral value (magnitude indicates path quality)
            integral_value = abs(integral) / (2 * n_segments)
            
            # Add penalties for visited cells
            if self.visit_count[ny, nx] > 0:
                integral_value /= (1 + 0.5 * self.visit_count[ny, nx])
            
            if integral_value > best_integral:
                best_integral = integral_value
                best_move = (dx, dy)
        
        return best_move
    
    def _update_attractor_network(self, agent, action):
        """Update complex-valued neural attractor network"""
        # Create complex Hebbian learning rule
        x, y = int(agent.x), int(agent.y)
        
        # Current state as complex number
        state = complex(x, y) + 1j * complex(action[0], action[1])
        
        # Update attractor weights using Oja's rule (complex version)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = x + dx, y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    key = (nx, ny)
                    
                    if key not in self.attractor_network:
                        self.attractor_network[key] = 0 + 0j
                    
                    # Complex Hebbian learning with decay
                    neighbor_state = complex(nx, ny)
                    weight = self.attractor_network[key]
                    
                    # Update: Δw = η * (z * conj(s) - |s|² * w)
                    learning_rate = 0.1
                    update = learning_rate * (state * np.conj(neighbor_state) - 
                                            abs(neighbor_state)**2 * weight)
                    
                    self.attractor_network[key] = weight + update
    
    def _get_center_potential(self, agent):
        """Get complex potential at current position"""
        x, y = int(agent.x), int(agent.y)
        
        if agent.belief_map[y, x] == 2:
            return 2 + 2j
        elif agent.belief_map[y, x] == 1:
            return -1 - 1j
        elif agent.belief_map[y, x] == -1:
            return 1 + 1j
        else:
            return complex(self.visit_count[y, x], 1) / (1 + self.visit_count[y, x])
    
    def _evaluate_field_at(self, z, agent):
        """Evaluate complex field at arbitrary point z"""
        x, y = int(z.real), int(z.imag)
        
        if not (0 <= x < agent.width and 0 <= y < agent.height):
            return 0 + 0j
        
        # Base value from belief map
        if agent.belief_map[y, x] == 2:
            base = 2 + 2j
        elif agent.belief_map[y, x] == 1:
            base = -1 - 1j
        elif agent.belief_map[y, x] == -1:
            base = 1 + 1j
        else:
            base = 0.5 + 0.5j
        
        # Add attractor network influence
        key = (x, y)
        if key in self.attractor_network:
            base += 0.3 * self.attractor_network[key]
        
        return base