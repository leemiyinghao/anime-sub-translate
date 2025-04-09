class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# Singleton cost tracker
class CostTracker(metaclass=Singleton):
    total_cost: float = 0

    def __init__(self):
        self.reset()

    def reset(self):
        self.total_cost = 0.0

    def add_cost(self, cost: float):
        self.total_cost += cost

    def get_cost(self) -> float:
        return self.total_cost
