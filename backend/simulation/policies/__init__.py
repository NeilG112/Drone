import os
import pkgutil
import importlib
import inspect
from .base import NavigationPolicy

POLICIES = {}

# 1. Iterate over all modules in the current package
package_dir = os.path.dirname(__file__)
for _, module_name, _ in pkgutil.iter_modules([package_dir]):
    # 2. Import the module
    module = importlib.import_module(f".{module_name}", package=__package__)
    
    # 3. Inspect module for NavigationPolicy subclasses
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, NavigationPolicy) and obj is not NavigationPolicy:
            # Register the policy
            # Use 'name' attribute if defined, else snake_case of class name (or just lower)
            # For backward compatibility with previous map:
            # RandomWalk -> 'random'
            # FrontierExploration -> 'frontier'
            # WallFollow -> 'wall_follow'
            
            # Simple heuristic mapping for now to match old keys:
            key_name = name.lower()
            if name == 'RandomWalk':
                key_name = 'random'
            elif name == 'FrontierExploration':
                key_name = 'frontier'
            elif name == 'WallFollow':
                key_name = 'wall_follow'
            
            # Allow class to define its own registry name via _registry_name or similar if we wanted to be fancy,
            # but for now let's just use the logic above + fallback to lower case.
            
            POLICIES[key_name] = obj
            
def get_policy(name):
    return POLICIES.get(name, POLICIES.get('random'))()
