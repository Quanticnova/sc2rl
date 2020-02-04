import sys
sys.path.insert(0, "../interface/")

import numpy as np

from agent import Agent, Memory

# 10 board, 7 additional, 6 action
NUM_CHANNELS = 23
POWERUP_RELEVANCE = 10
FLAME_RELEVANCE = 100


class RelGraphMemory(Memory):
    def __init__(self, buffer_len, discount):
        self.experiences = collections.deque(maxlen=buffer_len)
        self.discount = discount
        self.current_trajectory = []

    def push(self, state, action, reward, done):
        pass


class RelGraphAgent(Agent):
    def __init__(self,
        num_agents=2,
        board_size=8,
        init_eps=0.0001,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.init_eps = init_eps
        num_objects = board_size ** 2
        self.graph_dim = (num_agents, num_agents + num_objects)

        self.reset()

    def reset(self):
        self.prev_state = None
        self.prev_action = None
        self.prev_graph = np.random.random(self.graph_dim).astype('float32') + self.init_eps

    def state_space_converter(self, obs):
        board = obs['board']
        state = np.zeros((NUM_CHANNELS, board.shape[0], board.shape[1]), dtype=int)
        state_idx = 0

        board_indices = [0, 1, 2, 3, 4, 6, 7, 8, 10, 11]
        for b in board_indices:
            state[state_idx] = (board == b).astype(int)
            state_idx += 1
        
        additional_images = [
            'bomb_blast_strength',
            'bomb_life',
            'bomb_moving_direction',
            'flame_life',
            'ammo',
            'blast_strength',
            'can_kick',
        ]
        for im in additional_images:
            state[state_idx] = obs[im]
            state_idx += 1

        # one-hot action among 6 action channels, zero-hot if no previous
        if self.prev_action is not None:
            state[state_idx + self.prev_action] = 1
        state_idx += 6

        assert state_idx == state.shape[0], state_idx
        return state

    def action_space_converter(self, personal_action):
        raise NotImplementedError

    def _sample(self, state):
        raise NotImplementedError

    def _forward(self, state):
        raise NotImplementedError

    def train(self, run_settings):
        raise NotImplementedError

    def train_step(self, batch_size):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    def push_memory(self, state, action, reward, done):
        raise NotImplementedError

    @staticmethod
    def get_adjacent_flames(agent_frame, flames):
        adjacent = np.copy(agent_frame)

        loc = agent_frame.nonzero()
        if loc[0] > 0:
            adjacent[loc[0] - 1, loc[1]] = 1
        if loc[0] < adjacent.shape[0] - 1:
            adjacent[loc[0] + 1, loc[1]] = 1
        if loc[1] > 0:
            adjacent[loc[0], loc[1] - 1] = 1
        if loc[1] < adjacent.shape[1] - 1:
            adjacent[loc[0], loc[1] + 1] = 1

        return np.bitwise_and(adjacent, flames)

    @staticmethod
    def ground_truth_update(prev_state, curr_state, prev_graph, next_state, agent_id):
        curr_graph = np.copy(prev_graph)

        # ammo increase, range increase, or can kick pickup
        for idx in [14, 15, 16]:
            if (next_state[idx] > curr_state[idx]).all():
                next_loc = np.flatnonzero(next_state[8 + agent_id]).item()
                curr_graph[agent_id, next_loc] = POWERUP_RELEVANCE

        for agent in [0, 1]:
            # agent died
            if not next_state[8 + agent].any():
                agent_loc = curr_state[8 + agent]
                adj_flames = RelGraphAgent.get_adjacent_flames(agent_loc, next_state[4])
                for flame_idx in np.flatnonzero(adj_flames):
                    curr_graph[agent, flame_idx] = FLAME_RELEVANCE

        # TODO add relevance for kicking bombs

        return curr_graph