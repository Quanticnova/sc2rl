import custom_env
import random
from modified_state_space import state_modifier
import argparse
from models import DeepMind2017Net
import torch
import time

# Used to debug memory sizes
from pympler import asizeof

def default_test():

    env = custom_env.MinigameEnvironment(state_modifier.graph_conv_modifier,
                                            map_name_="DefeatRoaches",
                                            render=True,
                                            step_multiplier=8)
                                            
    
    topleft = [10, 10]
    botright = [20, 20]
    
    
    state, reward, done, _ = env.reset()
    
    while True:
        topleft = [random.randint(0,83), random.randint(0,83)]
        botright = [random.randint(0,83), random.randint(0,83)]
        action = random.randint(0, 4)
        state, reward, done, _ = env.step(action, topleft=topleft, botright=botright)
        if done:
            state, reward, done, _ = env.reset()    

def DeepMind2017Test():
    
    env = custom_env.MinigameEnvironment(state_modifier.modified_state_space,
                                            map_name_="DefeatRoaches",
                                            render=True,
                                            step_multiplier=8)
                                 
    nonspatial_act_size, spatial_act_depth = env.action_space
    
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    agent = DeepMind2017Net(nonspatial_act_size, spatial_act_depth, device).to(device)
    state, reward, done, _ = env.reset()
    screen, minimap, nonspatial_in, avail_actions = state
    print("loop beginning")
    while True:
        
        t1 = time.time()
        spatial_pol, nonspatial_pol, value, action = agent(screen, minimap, nonspatial_in, avail_actions, choosing=True)
        spatial_action, nonspatial_action = action
        #print("Action time: %f" % (time.time() - t1))
        
        t1 = time.time()
        state, reward, done, _ = env.step(nonspatial_action, spatial_action[0], spatial_action[1])
        #print("Env time: %f" % (time.time() - t1))
        if done:
            state, reward, done, _ = env.reset()
            
        screen, minimap, nonspatial_in, avail_actions = state
        
        print(asizeof.asizeof(state))
        
        
     
                                            
    



def main():

    method = 'default'    
    
    if (method == 'default'):
        default_test()
    elif (method == 'deepmind2017'):
        DeepMind2017Test()
    
if __name__ == "__main__":
    main()