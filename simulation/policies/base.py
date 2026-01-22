class NavigationPolicy:
    def select_action(self, agent):
        """Returns (dx, dy) tuple."""
        raise NotImplementedError
