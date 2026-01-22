from flask import Flask, render_template, jsonify, request
from simulation.engine import Simulation
from simulation.world import GridMap
from simulation.policies import get_policy, POLICIES
import random
import uuid
import os
import json
import glob
from datetime import datetime

import csv

import threading
import time

app = Flask(__name__)

# Data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Global Jobs Store
# { 'job_id': { 'status': 'running'|'completed'|'error', 'progress': 0, 'total': 100, 'result': None } }
JOBS = {}

@app.route('/api/policies', methods=['GET'])
def get_policies():
    return jsonify({'policies': list(POLICIES.keys())})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    try:
        data = request.json
        
        width = data.get('width', 100)
        height = data.get('height', 100)
        policy_name = data.get('policy', 'random')
        map_type = data.get('map_type', 'floorplan')
        complexity = float(data.get('complexity', 0.67))
        room_size = int(data.get('room_size', 15))
        num_rooms = int(data.get('map_num_rooms', 10))
        num_drones = int(data.get('num_drones', 1))
        num_targets = int(data.get('num_targets', 1))
        seed = data.get('seed', None)
        
        if seed is None:
            seed = random.randint(0, 100000)
        
        # Run single simulation
        sim_id = str(uuid.uuid4())
        result = _run_single_sim(width, height, policy_name, seed, map_type, complexity, room_size, num_rooms, num_drones, num_targets)
        
        # Save to timestamped folder: YYYYMMDD_HHMMSS_single_policy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{timestamp}_single_{policy_name}"
        _save_run(sim_id, result, folder_name)
        
        # Save Config for consistency (even single runs)
        _save_batch_config(folder_name, {
            'type': 'single',
            'width': width,
            'height': height,
            'policy': policy_name,
            'map_type': map_type,
            'complexity': complexity,
            'num_drones': num_drones,
            'num_targets': num_targets,
            'timestamp': timestamp
        })
        
        return jsonify({
            'id': sim_id,
            'config': result['config'],
            'stats': result['stats'],
            'history': result['history'],
            'map': result['map']
        })
    except Exception as e:
        import traceback
        print(f"ERROR in /api/simulate: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/benchmark', methods=['POST'])
def start_benchmark():
    data = request.json
    width = int(data.get('width', 100))
    height = int(data.get('height', 100))
    policy_name = data.get('policy', 'random')
    num_runs = int(data.get('num_runs', 5))
    map_type = data.get('map_type', 'floorplan')
    complexity = float(data.get('complexity', 0.67))
    room_size = int(data.get('room_size', 15))
    num_rooms = int(data.get('map_num_rooms', 10))
    num_drones = int(data.get('num_drones', 1))
    num_targets = int(data.get('num_targets', 1))
    
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'running', 'progress': 0, 'total': num_runs, 'result': None}
    
    thread = threading.Thread(target=_run_benchmark_background, args=(job_id, width, height, policy_name, num_runs, map_type, complexity, room_size, num_rooms, num_drones, num_targets))
    thread.start()
    
    return jsonify({'job_id': job_id})

def _run_benchmark_background(job_id, width, height, policy_name, num_runs, map_type, complexity, room_size, num_rooms, num_drones, num_targets):
    try:
        # Create a batch folder name: YYYYMMDD_HHMMSS_benchmark_policy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_name = f"{timestamp}_benchmark_{policy_name}"
        
        results_summary = []
        
        for i in range(num_runs):
            seed = random.randint(0, 100000)
            sim_id = str(uuid.uuid4())
            
            # Run simulation
            result = _run_single_sim(width, height, policy_name, seed, map_type, complexity, room_size, num_rooms, num_drones, num_targets)
            
            # Save to batch folder
            _save_run(sim_id, result, batch_name)
            
            # Add to summary
            stats = result['stats']
            results_summary.append({
                'id': sim_id,
                'success': stats['success'],
                'steps': stats['steps'],
                'seed': seed,
                'policy': policy_name,
                'coverage': stats.get('coverage_percent', 0),
                'density': stats.get('obstacle_density', 0),
                'unique_visited': stats.get('unique_visited', 0),
                'targets_found': stats['targets_found'],
                'efficiency': stats.get('efficiency', 0),
                'turns': stats.get('turns', 0),
                'collisions': stats.get('collisions', 0),
                'num_drones': stats.get('num_drones', 1),
                'revisits': stats.get('revisits', 0),
                'max_cell_visits': stats.get('max_cell_visits', 0),
                'avg_visits_per_cell': stats.get('avg_visits_per_cell', 0),
                'avg_info_gain': stats.get('avg_information_gain', 0),
                'turn_rate': stats.get('turn_rate', 0),
                'collision_rate': stats.get('collision_rate', 0),
                'max_steps_without_new_info': stats.get('max_steps_without_new_info', 0)
            })
            
            # Update Progress
            JOBS[job_id]['progress'] = i + 1
            
        # Write CSV Summary
        _write_csv_summary(batch_name, results_summary)
        
        # Save Batch Config
        _save_batch_config(batch_name, {
            'type': 'benchmark',
            'width': width,
            'height': height,
            'num_runs': num_runs,
            'policy': policy_name,
            'map_type': map_type,
            'complexity': complexity,
            'room_size': room_size,
            'num_rooms': num_rooms,
            'num_drones': num_drones,
            'num_targets': num_targets,
            'timestamp': timestamp
        })
        
        JOBS[job_id]['result'] = {
            'batch_name': batch_name,
            'runs': results_summary
        }
        JOBS[job_id]['status'] = 'completed'
        
    except Exception as e:
        print(f"Benchmark Job Failed: {e}")
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(e)


@app.route('/api/compare', methods=['POST'])
def start_compare():
    data = request.json
    width = int(data.get('width', 100))
    height = int(data.get('height', 100))
    num_runs = int(data.get('num_runs', 5))
    map_type = data.get('map_type', 'floorplan')
    complexity = float(data.get('complexity', 0.67))
    room_size = int(data.get('room_size', 15))
    num_rooms = int(data.get('map_num_rooms', 10))
    num_drones = int(data.get('num_drones', 1))
    num_targets = int(data.get('num_targets', 1))
    requested_policies = data.get('policies', [])
    
    # Validation/Default
    available_policies = list(POLICIES.keys())
    if not requested_policies:
        policies = available_policies
    else:
        policies = [p for p in requested_policies if p in available_policies]
        if not policies:
            policies = available_policies
            
    job_id = str(uuid.uuid4())
    total_steps = num_runs * len(policies)
    JOBS[job_id] = {'status': 'running', 'progress': 0, 'total': total_steps, 'result': None}
    
    thread = threading.Thread(target=_run_compare_background, args=(job_id, width, height, num_runs, policies, map_type, complexity, room_size, num_rooms, num_drones, num_targets))
    thread.start()
    
    return jsonify({'job_id': job_id})

def _run_compare_background(job_id, width, height, num_runs, policies, map_type, complexity, room_size, num_rooms, num_drones, num_targets):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_name = f"{timestamp}_compare_custom"
        
        results = {p: {'success_rate': 0, 'avg_steps': 0, 'runs': []} for p in policies}
        all_runs_flat = [] 
        
        # Generate seeds first
        seeds = [random.randint(0, 100000) for _ in range(num_runs)]
        
        progress_count = 0
        
        for seed in seeds:
            for policy_name in policies:
                sim_id = str(uuid.uuid4())
                result = _run_single_sim(width, height, policy_name, seed, map_type, complexity, room_size, num_rooms, num_drones, num_targets)
                
                # Save run
                _save_run(sim_id, result, batch_name)
                
                stats = result['stats']
                run_summary = {
                    'id': sim_id,
                    'seed': seed,
                    'policy': policy_name,
                    'success': stats['success'],
                    'steps': stats['steps'],
                    'coverage': stats.get('coverage_percent', 0),
                    'density': stats.get('obstacle_density', 0),
                    'unique_visited': stats.get('unique_visited', 0),
                    'targets_found': stats['targets_found'],
                    'efficiency': stats.get('efficiency', 0),
                    'turns': stats.get('turns', 0),
                    'collisions': stats.get('collisions', 0),
                    'num_drones': stats.get('num_drones', 1),
                    'revisits': stats.get('revisits', 0),
                    'max_cell_visits': stats.get('max_cell_visits', 0),
                    'avg_visits_per_cell': stats.get('avg_visits_per_cell', 0),
                    'avg_info_gain': stats.get('avg_information_gain', 0),
                    'turn_rate': stats.get('turn_rate', 0),
                    'collision_rate': stats.get('collision_rate', 0),
                    'max_steps_without_new_info': stats.get('max_steps_without_new_info', 0)
                }
                
                # Aggregate stats
                results[policy_name]['runs'].append(run_summary)
                all_runs_flat.append(run_summary)
                
                progress_count += 1
                JOBS[job_id]['progress'] = progress_count
                
        # Write CSV Summary
        _write_csv_summary(batch_name, all_runs_flat)
        
        # Save Batch Config
        _save_batch_config(batch_name, {
            'type': 'compare',
            'width': width,
            'height': height,
            'num_runs': num_runs,
            'policies': policies,
            'map_type': map_type,
            'complexity': complexity,
            'num_drones': num_drones,
            'num_targets': num_targets,
            'timestamp': timestamp
        })
                
        # Calculate final stats (for UI)
        summary = []
        for p in policies:
            runs = results[p]['runs']
            success_count = sum(1 for r in runs if r['success'])
            step_counts = [r['steps'] for r in runs if r['success']] 
            avg_steps = sum(step_counts) / len(step_counts) if step_counts else 0
            
            # New Averages
            turns_counts = [r['turns'] for r in runs]
            avg_turns = sum(turns_counts) / num_runs
            
            coll_counts = [r['collisions'] for r in runs]
            avg_coll = sum(coll_counts) / num_runs
            
            eff_counts = [r['efficiency'] for r in runs]
            avg_eff = sum(eff_counts) / num_runs
            
            summary.append({
                'policy': p,
                'success_rate': (success_count / num_runs) * 100,
                'avg_steps': round(avg_steps, 2),
                'avg_turns': round(avg_turns, 2),
                'avg_collisions': round(avg_coll, 2),
                'avg_efficiency': round(avg_eff, 3),
                'runs': runs
            })
            
        JOBS[job_id]['result'] = {
            'batch_name': batch_name,
            'summary': summary
        }
        JOBS[job_id]['status'] = 'completed'
        
    except Exception as e:
        print(f"Compare Job Failed: {e}")
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(e)

@app.route('/api/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns list of benchmark folders."""
    folders = []
    if os.path.exists(DATA_DIR):
        for name in os.listdir(DATA_DIR):
            path = os.path.join(DATA_DIR, name)
            if os.path.isdir(path):
                # Count runs
                files = glob.glob(os.path.join(path, "*.json"))
                folders.append({
                    'name': name,
                    'count': len(files),
                    'path': name # relative to data dir
                })
    # Sort by name (timestamp) descending
    folders.sort(key=lambda x: x['name'], reverse=True)
    return jsonify({'folders': folders})

@app.route('/api/history/<folder_name>', methods=['GET'])
def get_folder_runs(folder_name):
    """Returns runs in a specific folder along with batch config."""
    folder_path = os.path.join(DATA_DIR, folder_name)
    runs = []
    config = {}
    
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Try to load config.json
        config_path = os.path.join(folder_path, 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error reading config.json: {e}")
        
        files = glob.glob(os.path.join(folder_path, "*.json"))
        for fpath in files:
            if os.path.basename(fpath) == 'config.json' or os.path.basename(fpath) == 'summary.csv':
                continue
                
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                    stats = data['stats']
                    # Summary info only
                    runs.append({
                        'id': os.path.splitext(os.path.basename(fpath))[0],
                        'success': stats['success'],
                        'steps': stats['steps'],
                        'seed': data['config']['seed'],
                        'policy': data['config']['policy'],
                        'coverage': stats.get('coverage_percent', 0),
                        'efficiency': stats.get('efficiency', 0),
                        'turns': stats.get('turns', 0),
                        'collisions': stats.get('collisions', 0),
                        'revisits': stats.get('revisits', 0),
                        'max_cell_visits': stats.get('max_cell_visits', 0),
                        'avg_visits_per_cell': stats.get('avg_visits_per_cell', 0),
                        'avg_info_gain': stats.get('avg_information_gain', 0),
                        'turn_rate': stats.get('turn_rate', 0),
                        'collision_rate': stats.get('collision_rate', 0),
                        'max_steps_without_new_info': stats.get('max_steps_without_new_info', 0)
                    })
            except Exception as e:
                print(f"Error reading {fpath}: {e}")
                
    return jsonify({'runs': runs, 'config': config})
    
def _save_batch_config(folder_name, config_data):
    folder_path = os.path.join(DATA_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    with open(os.path.join(folder_path, 'config.json'), 'w') as f:
        json.dump(config_data, f, indent=2)

@app.route('/api/history/<folder_name>/download', methods=['GET'])
def download_folder_csv(folder_name):
    """Downloads the summary.csv file for a specific folder."""
    folder_path = os.path.join(DATA_DIR, folder_name)
    csv_path = os.path.join(folder_path, "summary.csv")
    
    if os.path.exists(csv_path):
        from flask import send_file
        return send_file(csv_path, as_attachment=True, download_name=f"{folder_name}_summary.csv")
    else:
        return jsonify({'error': 'CSV file not found'}), 404

def _write_csv_summary(folder_name, runs):
    folder_path = os.path.join(DATA_DIR, folder_name)
    csv_path = os.path.join(folder_path, "summary.csv")
    
    if not runs:
        return
        
    headers = [
        'id', 'policy', 'seed', 'success', 'steps', 'coverage', 'density', 
        'unique_visited', 'targets_found', 'efficiency', 'turns', 'collisions',
        'revisits', 'max_cell_visits', 'avg_visits_per_cell', 'avg_info_gain',
        'turn_rate', 'collision_rate', 'max_steps_without_new_info'
    ]
    
    try:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(runs)
        print(f" [CSV] Successfully saved summary.csv with {len(runs)} rows to {folder_name}")
    except Exception as e:
        print(f" [CSV] Failed to write CSV to {csv_path}: {e}") 



@app.route('/api/simulation/<sim_id>', methods=['GET'])
def get_simulation(sim_id):
    # Search for the file in all subdirectories of data
    # Using glob might be expensive if many files, but okay for this scale
    matches = glob.glob(os.path.join(DATA_DIR, '**', f"{sim_id}.json"), recursive=True)
    
    if matches:
        file_path = matches[0]
        try:
            with open(file_path, 'r') as f:
                result = json.load(f)
            return jsonify({
                'id': sim_id,
                'config': result['config'],
                'stats': result['stats'],
                'history': result['history'],
                'map': result['map']
            })
        except Exception as e:
             return jsonify({'error': f"Failed to load file: {str(e)}"}), 500
             
    return jsonify({'error': 'Simulation not found'}), 404

def _save_run(sim_id, result, folder_name):
    folder_path = os.path.join(DATA_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    
    file_path = os.path.join(folder_path, f"{sim_id}.json")
    with open(file_path, 'w') as f:
        json.dump(result, f)

def _run_single_sim(width, height, policy_name, seed, map_type='floorplan', complexity=0.67, room_size=15, num_rooms=10, num_drones=1, num_targets=1):
    # Initialize simulation components
    world = GridMap(width, height, map_type=map_type, complexity=complexity, room_size=room_size, num_rooms=num_rooms, num_targets=num_targets, seed=seed)
    policy = get_policy(policy_name)
    
    # Run simulation with multi-drone support
    sim = Simulation(world, policy, num_drones=num_drones)
    result = sim.run()
    
    return {
        'config': {
            'width': width,
            'height': height,
            'seed': seed,
            'policy': policy_name,
            'map_type': map_type,
            'complexity': complexity,
            'room_size': room_size,
            'num_rooms': num_rooms,
            'num_drones': num_drones,
            'num_targets': num_targets
        },
        'stats': result['stats'],
        'history': result['history'],
        'map': world.to_dict()
    }

if __name__ == '__main__':
    app.run(debug=True)
