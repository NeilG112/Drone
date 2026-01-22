import random
from collections import deque
from .base import NavigationPolicy


class GlobalUtilityFrontierExploration(NavigationPolicy):
    """
    Frontier exploration optimized for speed:

    - single BFS (like baseline)
    - prune frontier set
    - cheap region proxy
    - no nested BFS
    """

    def __init__(self,
                 unknown_weight=1.8,
                 ray_weight=0.4,
                 distance_weight=1.0,
                 obstacle_weight=4.0,
                 max_frontiers=40,
                 commitment_ratio=1.25):

        self.unknown_weight = unknown_weight
        self.ray_weight = ray_weight
        self.distance_weight = distance_weight
        self.obstacle_weight = obstacle_weight
        self.max_frontiers = max_frontiers
        self.commitment_ratio = commitment_ratio

        self.current_goal = None

    # ---------------------------------------------------------

    def select_action(self, agent):

        start = (agent.x, agent.y)

        parents, dists, frontiers = self._bfs_find_frontiers(agent)

        if not frontiers:
            return (0, 0)

        # keep only closest K frontiers
        frontiers.sort(key=lambda p: dists[p])
        frontiers = frontiers[:self.max_frontiers]

        best, best_score = self._choose_best_frontier(
            frontiers, dists, agent)

        # commitment hysteresis
        if self.current_goal in frontiers:

            old_score = self._score_frontier(
                self.current_goal[0],
                self.current_goal[1],
                dists[self.current_goal],
                agent)

            if best_score < old_score * self.commitment_ratio:
                best = self.current_goal

        self.current_goal = best

        return self._first_step(start, best, parents)

    # ---------------------------------------------------------

    def _bfs_find_frontiers(self, agent):

        start = (agent.x, agent.y)

        q = deque([start])
        parents = {start: None}
        dists = {start: 0}

        frontiers = []

        moves = [(0, -1), (1, 0), (0, 1), (-1, 0)]

        while q:

            x, y = q.popleft()

            # frontier test
            for dx, dy in moves:
                nx, ny = x + dx, y + dy
                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if agent.belief_map[ny, nx] == -1:
                        frontiers.append((x, y))
                        break

            # BFS expand through free space
            for dx, dy in moves:
                nx, ny = x + dx, y + dy

                if 0 <= nx < agent.width and 0 <= ny < agent.height:
                    if (nx, ny) not in parents \
                       and agent.belief_map[ny, nx] == 0:

                        parents[(nx, ny)] = (x, y)
                        dists[(nx, ny)] = dists[(x, y)] + 1
                        q.append((nx, ny))

        return parents, dists, frontiers

    # ---------------------------------------------------------

    def _choose_best_frontier(self, frontiers, dists, agent):

        best = None
        best_score = -float("inf")

        for fx, fy in frontiers:

            score = self._score_frontier(
                fx, fy, dists[(fx, fy)], agent)

            if score > best_score:
                best_score = score
                best = (fx, fy)

        return best, best_score

    # ---------------------------------------------------------

    def _score_frontier(self, x, y, dist, agent):

        local_unknown = self._unknown_around(x, y, agent, r=3)
        ray_unknown = self._ray_probe_unknown(x, y, agent, length=8)
        obstacle_penalty = self._obstacle_adjacent(x, y, agent)

        score = (
            self.unknown_weight * local_unknown
            + self.ray_weight * ray_unknown
            - self.distance_weight * dist
            - self.obstacle_weight * obstacle_penalty
        )

        return score

    # ---------------------------------------------------------

    def _unknown_around(self, x, y, agent, r):

        cnt = 0
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):

                cx, cy = x + dx, y + dy
                if 0 <= cx < agent.width and 0 <= cy < agent.height:
                    if agent.belief_map[cy, cx] == -1:
                        cnt += 1
        return cnt

    # ---------------------------------------------------------

    def _ray_probe_unknown(self, x, y, agent, length):

        total = 0

        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:

            cx, cy = x, y

            for _ in range(length):
                cx += dx
                cy += dy

                if not (0 <= cx < agent.width and 0 <= cy < agent.height):
                    break

                if agent.belief_map[cy, cx] == 1:
                    break

                if agent.belief_map[cy, cx] == -1:
                    total += 1

        return total

    # ---------------------------------------------------------

    def _obstacle_adjacent(self, x, y, agent):

        p = 0
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:

            nx, ny = x + dx, y + dy
            if 0 <= nx < agent.width and 0 <= ny < agent.height:
                if agent.belief_map[ny, nx] == 1:
                    p += 1
        return p

    # ---------------------------------------------------------

    def _first_step(self, start, goal, parents):

        cur = goal

        while parents[cur] != start:
            cur = parents[cur]

        sx, sy = start
        nx, ny = cur

        return (nx - sx, ny - sy)
