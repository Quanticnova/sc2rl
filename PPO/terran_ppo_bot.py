
from pysc2.agents import base_agent
from pysc2.env import sc2_env
from pysc2.lib import actions, features, units
from absl import app
import random
import enhancedbaseagent
from enhancedbaseagent import EnhancedBaseAgent

class terran_agent(EnhancedBaseAgent):
    def __init__(self):
        super(terran_agent, self).__init__()
        self.attack_coordinates = None
        self.iteration = 0
        
    def step(self, obs):
        self.iteration += 1
        super(terran_agent, self).step(obs)
        
        if self.unit_type_is_selected(obs, units.Terran.Marine) and self.iteration % 20 == 0:
            return self.handle_action(obs)
        else:
            return self.select_units_by_type(obs, units.Terran.Marine)
            
        self.iteration += 1
        print("--- Returning no_op ---")
        return actions.FUNCTIONS.no_op()
        
    # Implement this     
    def handle_action(self, 
                        obs):
        print("--- handle_action called ---")
        x = random.randint(0,50)
        y = random.randint(0,50)
        return actions.FUNCTIONS.Attack_screen("now", (x,y))






STEP_MUL=1

def main(unused_argv):
    agent = terran_agent()
    try:
        DZaB_data = enhancedbaseagent.run_game_with_agent(agent, "DefeatZerglingsAndBanelings", 1)
        DR_data = enhancedbaseagent.run_game_with_agent(agent, "DefeatRoaches", 1)
                    
    except KeyboardInterrupt:
        pass
        
if __name__ == "__main__":
    app.run(main)
