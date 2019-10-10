import sys
sys.path.insert(0, "../interface/")

from agent import Agent
from pommerman import constants, utility

class NoopAgent(Agent):
    def __init__(self):
        # Intentionally bypassing parent constructor
        pass

    def _sample(self, state):
        return constants.Action.Stop

    def _forward(self, state):
        return self._sample(state)

    def state_space_converter(self, state):
        return state

    def action_space_converter(self, action):
        return action

    def train(self, run_settings):
        pass

    def train_step(self, batch_size):
        pass

    def save(self):
        pass
    
    def push_memory(self, state, action, reward, done):
        pass