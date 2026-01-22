"""
Performance profiling utilities for map generation and simulation.
"""
import time
from functools import wraps


def timing_decorator(func):
    """Decorator to measure and print execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_time = time.perf_counter() - start_time
        print(f"[TIMING] {func.__name__} took {elapsed_time*1000:.2f}ms")
        return result
    return wrapper


class PerformanceTimer:
    """Context manager for timing code blocks."""
    def __init__(self, name="Operation"):
        self.name = name
        self.start_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time
        print(f"[TIMING] {self.name} took {self.elapsed*1000:.2f}ms")
        return False


def benchmark_map_generation(width, height, map_type='floorplan', iterations=100, **kwargs):
    """
    Benchmark map generation performance.
    
    Args:
        width: Map width
        height: Map height
        map_type: Type of map ('random' or 'floorplan')
        iterations: Number of iterations to run
        **kwargs: Additional arguments for GridMap (complexity, room_size, num_rooms, etc.)
    
    Returns:
        dict: Benchmark results with timing statistics
    """
    from simulation.world import GridMap
    import numpy as np
    
    times = []
    
    print(f"\n{'='*60}")
    print(f"Benchmarking {map_type} map generation: {width}x{height}")
    print(f"Iterations: {iterations}")
    print(f"Parameters: {kwargs}")
    print(f"{'='*60}\n")
    
    for i in range(iterations):
        start = time.perf_counter()
        GridMap(width, height, map_type=map_type, seed=i, **kwargs)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{iterations} iterations complete...")
    
    times_array = np.array(times)
    results = {
        'iterations': iterations,
        'total_time': np.sum(times_array),
        'avg_time': np.mean(times_array),
        'min_time': np.min(times_array),
        'max_time': np.max(times_array),
        'std_time': np.std(times_array),
        'median_time': np.median(times_array)
    }
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Total Time:   {results['total_time']:.3f}s")
    print(f"  Average:      {results['avg_time']*1000:.2f}ms")
    print(f"  Median:       {results['median_time']*1000:.2f}ms")
    print(f"  Min:          {results['min_time']*1000:.2f}ms")
    print(f"  Max:          {results['max_time']*1000:.2f}ms")
    print(f"  Std Dev:      {results['std_time']*1000:.2f}ms")
    print(f"{'='*60}\n")
    
    return results


if __name__ == '__main__':
    # Example usage
    print("Running performance benchmarks...\n")
    
    # Benchmark different map sizes
    sizes = [(20, 20), (50, 50), (100, 100)]
    
    for w, h in sizes:
        benchmark_map_generation(
            w, h,
            map_type='floorplan',
            iterations=100,
            complexity=0.3,
            room_size=5,
            num_rooms=8
        )
