import unittest

from cost import CostTracker


class TestCostTracker(unittest.TestCase):
    def setUp(self):
        # Reset the singleton before each test
        CostTracker().reset()

    def test_singleton_pattern(self):
        # Test that multiple instances are the same object
        tracker1 = CostTracker()
        tracker2 = CostTracker()
        self.assertIs(tracker1, tracker2)

    def test_initial_cost(self):
        # Test that the initial cost is zero
        tracker = CostTracker()
        self.assertEqual(tracker.get_cost(), 0.0)

    def test_add_cost(self):
        # Test adding costs
        tracker = CostTracker()
        tracker.add_cost(10.5)
        self.assertEqual(tracker.get_cost(), 10.5)
        
        # Add more cost
        tracker.add_cost(5.25)
        self.assertEqual(tracker.get_cost(), 15.75)

    def test_reset(self):
        # Test resetting the cost
        tracker = CostTracker()
        tracker.add_cost(20.0)
        self.assertEqual(tracker.get_cost(), 20.0)
        
        tracker.reset()
        self.assertEqual(tracker.get_cost(), 0.0)

    def test_singleton_shared_state(self):
        # Test that the state is shared between instances
        tracker1 = CostTracker()
        tracker1.add_cost(15.0)
        
        tracker2 = CostTracker()
        self.assertEqual(tracker2.get_cost(), 15.0)
        
        tracker2.add_cost(5.0)
        self.assertEqual(tracker1.get_cost(), 20.0)


if __name__ == "__main__":
    unittest.main()
