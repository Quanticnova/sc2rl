from pysc2.env import sc2_env
from pysc2.lib import features
from action_interface import Action, Actuator
from numpy import all as np_all
import numpy as np

class MinigameEnvironment:

    def __init__(self, state_modifier_func, map_name_="DefeatRoaches", render=False, step_multiplier=None):
        '''
        Initializes internal pysc2 environment
        :param render: Whether to render the game
        :param step_multiplier: Step multiplier for pysc2 environment
        '''
        import sys
        from absl import flags
        FLAGS = flags.FLAGS
        FLAGS(sys.argv)
        self.map = map_name_
        self.state_modifier_func = state_modifier_func

        self._env = sc2_env.SC2Env(
            map_name=map_name_,
            agent_interface_format=features.AgentInterfaceFormat(
                feature_dimensions=features.Dimensions(screen=84, minimap=64),
                use_feature_units=True
            ),
            step_mul=step_multiplier,
            visualize=render,
            game_steps_per_episode=None
        )
        self._actuator = Actuator()
        self._prev_frame = None
        self._curr_frame = None
        self._terminal = True

        self.action_space = self._actuator.action_space()
        FACTOR = 9 # TODO
        self.observation_space = [84, 84, FACTOR] # 

    def reset(self):
        '''
        Resets the environment for a new episode
        :returns: Observations, reward, terminal, None for start state
        '''
        self._actuator.reset()
        self._terminal = False

        raw_obs = self._run_to_next()
        self._terminal = raw_obs.last()
        agent_obs = self._combine_frames()
        return agent_obs, raw_obs.reward, raw_obs.last(), None # exclude selected

    def step(self, action):
        '''
        Runs the environment until the next agent action is required
        :param action: 0 for Action.RETREAT or 1 for Action.ATTACK
        :returns: Observations, reward, terminal, None
        '''
        
        assert not self._terminal, 'Environment must be reset after init or terminal'
        #assert action == Action.ATTACK or action == Action.RETREAT, 'Agent action must be attack or retreat'
        if (action == 0):
            step_act = Action.RETREAT
        if (action == 1):
            step_act = Action.ATTACK
        
        raw_obs = self._run_to_next(step_act)
        self._terminal = raw_obs.last()
        agent_obs = self._combine_frames()
        return agent_obs, raw_obs.reward, raw_obs.last(), None # exclude selected

    def _run_to_next(self, start_action=None):
        '''
        Runs the environment with NO_OPs and SELECTs until the next agent action is required
        :param start_action: The chosen agent action, or None for reset
        :returns: Final raw observations
        '''
        if start_action is None:
            raw_obs = self._reset_env()
        else:
            last_obs = self.state_modifier_func(self._curr_frame)
            raw_action = self._actuator.compute_action(start_action, last_obs)
            raw_obs = self._step_env(raw_action)
        
        if raw_obs.last():
            return raw_obs
        
        custom_obs = self.state_modifier_func(raw_obs)

        friendly_unit_density = custom_obs[2]
        assert not np_all(friendly_unit_density == 0), 'All marines dead but not terminal state'

        selected = custom_obs[0]
        if not self._actuator.units_selected or np_all(selected == 0):
            raw_action = self._actuator.compute_action(Action.SELECT, custom_obs)
            raw_obs = self._step_env(raw_action)
        assert self._actuator.units_selected, 'Units not selected after select action'
        return raw_obs

    def _combine_frames(self):
        '''
        Combines the previous and current frame for observations
        '''
        assert self._prev_frame is not None and self._curr_frame is not None, 'Returning to agent after less than 2 frames should be impossible'

        custom_prev = self.state_modifier_func(self._prev_frame)[1:]
        custom_curr = self.state_modifier_func(self._curr_frame)
        custom_curr = custom_curr[np.r_[1:len(custom_curr),0]] # move selected frame to end
        custom_frames = np.append(custom_prev, custom_curr, axis=0)
        return custom_frames

    def _reset_env(self):
        self._prev_frame = self._curr_frame
        self._curr_frame = self._env.reset()[0] # get obs for 1st agent
        return self._curr_frame

    def _step_env(self, raw_action):
        self._prev_frame = self._curr_frame
        self._curr_frame = self._env.step([raw_action])[0] # get obs for 1st agent
        return self._curr_frame
        
        
        
        
        
