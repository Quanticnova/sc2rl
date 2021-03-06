from enum import Enum

import numpy as np
from pysc2.env import sc2_env
from pysc2.lib import features, protocol, units

from action_interface import BuildMarinesAction, BuildMarinesActuator
from abstract_core import CustomEnvironment

class BuildMarinesEnvironment(CustomEnvironment):
    SCREEN_SIZE = 84
    MINIMAP_SIZE = 1
    MAP = 'BuildMarines'

    def __init__(self,
            render=False,
            step_multiplier=None,
            enable_scv_helper=True,
            enable_kill_helper=True,
        ):
        '''
        :param render: Whether to render the game
        :param step_multiplier: Step multiplier for pysc2 environment
        :param enable_scv_helper: Auto-make SCVs
        :param enable_kill_helper: Auto-kill Marines
        '''

        self.render = render
        self.step_multiplier = step_multiplier
        self.enable_scv_helper = enable_scv_helper
        self.enable_kill_helper = enable_kill_helper

        self._actuator = BuildMarinesActuator()
        self._prev_frame = None
        self._curr_frame = None
        self._terminal = True
        self._accumulated_reward = 0

    def reset(self):
        '''
        Resets the environment for a new episode
        :returns: Observations, reward, terminal, None for start state
        '''
        self._create_env()

        self._actuator.reset()
        self._terminal = False
        self._accumulated_reward = 0

        self._reset_env()
        self._run_helpers()
        
        return [self._curr_frame], [self._accumulated_reward], self._terminal, [None]

    def step(self, action_list):
        '''
        Runs the environment until the next agent action is required
        :param action: 0 for Action.RETREAT or 1 for Action.ATTACK
        :returns: Observations, reward, terminal, None
        '''
        assert not self._terminal, 'Environment must be reset after init or terminal'
        self._accumulated_reward = 0
        
        action = action_list[0]
        # Convert to Enum
        action = BuildMarinesAction(action)

        self._run_to_next(action)
        self._run_helpers()
        
        return [self._curr_frame], [self._accumulated_reward], self._terminal, [None]

    def _create_env(self):
        '''
        Initializes internal pysc2 environment
        '''
        import sys
        from absl import flags
        FLAGS = flags.FLAGS
        FLAGS(sys.argv)

        self._env = sc2_env.SC2Env(
            map_name=self.MAP,
            agent_interface_format=features.AgentInterfaceFormat(
                feature_dimensions=features.Dimensions(
                    screen=self.SCREEN_SIZE, minimap=self.MINIMAP_SIZE),
                use_feature_units=True
            ),
            step_mul=self.step_multiplier,
            visualize=self.render,
            game_steps_per_episode=None
        )

    def _run_helpers(self):
        checks_cleared = False
        while not checks_cleared and not self._terminal:
            checks_cleared = True
            if self._curr_frame.observation.player.idle_worker_count > 0:
                checks_cleared = False
                self._run_to_next(BuildMarinesAction.RALLY_SCVS)
            if self.enable_scv_helper and self._should_make_scv(self._curr_frame):
                checks_cleared = False
                self._run_to_next(BuildMarinesAction.MAKE_SCV)
            if self.enable_kill_helper and self._should_kill_marine(self._curr_frame):
                checks_cleared = False
                self._run_to_next(BuildMarinesAction.KILL_MARINE)

    def _run_to_next(self, start_action):
        assert not self._terminal, 'Entered _run_to_next at terminal'
        raw_action = self._actuator.compute_action(start_action, self._curr_frame)
        self._step_env(raw_action)
        
        while self._actuator.in_progress is not None:
            if self._terminal:
                return

            raw_action = self._actuator.compute_action(start_action, self._curr_frame)
            self._step_env(raw_action)
    
    def _reset_env(self):
        self._prev_frame = self._curr_frame
        # Get obs for 1st agent
        self._curr_frame = self._env.reset()[0]
        self._accumulated_reward += self._curr_frame.reward
        if self._curr_frame.last():
            self._terminal = True

    def _step_env(self, raw_action):
        self._prev_frame = self._curr_frame
        try:
            # Get obs for 1st agent
            self._curr_frame = self._env.step([raw_action])[0]
        except protocol.ConnectionError:
            self._curr_frame = self._env.reset()[0]
        self._accumulated_reward += self._curr_frame.reward
        if self._curr_frame.last():
            self._terminal = True

    @staticmethod
    def _should_make_scv(obs):
        '''
        Checks if an SCV should be made
        (enough minerals, not supply blocked, less than optimal number,
        no SCV queued or CC not selected)
        '''
        if (obs.observation.player.minerals < BuildMarinesActuator.SCV_COST
                or obs.observation.player.food_used == obs.observation.player.food_cap
                or obs.observation.player.food_workers >= BuildMarinesActuator.MAX_SCVS):
            return False
        if obs.observation.single_select[0].unit_type != units.Terran.CommandCenter.value:
            return True
        return len(obs.observation.build_queue) == 0

    @staticmethod
    def _should_kill_marine(obs):
        '''
        Checks if an attack should be queued (less than 50 minerals, enough marines)
        '''
        PIXELS_PER_RAX = 110

        rax_pixels = np.sum(obs.observation.feature_screen.unit_type == units.Terran.Barracks.value)
        num_rax = rax_pixels // PIXELS_PER_RAX
        num_marines = obs.observation.player.food_army - num_rax
        multiple_marines = num_marines >= 2

        few_mins = obs.observation.player.minerals < BuildMarinesActuator.MARINE_COST
        capped = obs.observation.player.food_used == obs.observation.player.food_cap
        return multiple_marines and (few_mins or capped)