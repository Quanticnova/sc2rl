from custom_env import MinigameEnvironment
from modified_state_space import state_modifier
import random
import time

def random_agent():
    env = MinigameEnvironment(render=True,step_multiplier=2,state_modifier_func=state_modifier.modified_state_space)
    state, reward, done, _ = env.reset()
    print(state.shape)
    for i in range(10): 
        while (not done):
            time.sleep(0.1)
            action = random.randint(0, 6)
            state, reward, done, _ = env.step(action)
        state, reward, done, _ = env.reset()

def main():
    random_agent()
    
if __name__ == "__main__":
    main()
