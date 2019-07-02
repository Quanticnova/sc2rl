from agent import Agent, Model, Memory, AgentSettings
from config import GraphConvConfigMinigames
from modified_state_space import state_modifier
import utils

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

import copy


class PPOAgent(Agent):

    """
        Constructor for PPO
    """

    def __init__(self, model, settings, memory, PPO_settings):
        super().__init__(model, settings, memory)
        self.step = 0
        self.frame_count = 0
        self.epochs_trained = 0
        self.PPO_settings = PPO_settings
        self.target_model = copy.deepcopy(model)
        self.hidden_state = self.model.init_hidden(use_torch=False)
        self.prev_hidden_state = None
        self.optimizer = settings.optimizer(model.parameters(), lr=settings.learning_rate)
        self.action = [np.array([[0,0],[0,0]]),0]
        self.config = GraphConvConfigMinigames
        self.value = 0
        self.loss = nn.MSELoss().to(PPO_settings['device'])
    
    def _forward(self, agent_state, choosing=False):
        (G, X, avail_actions) = agent_state
        self.prev_action = utils.action_to_onehot(self.action, self.config.action_space, self.config.spatial_width)
        self.prev_hidden_state = copy.deepcopy(self.hidden_state)
        _, _, value, self.hidden_state, action = self.model(np.expand_dims(G, 1),
                                                    np.expand_dims(X, 1),
                                                    avail_actions,
                                                    self.hidden_state,
                                                    np.expand_dims(self.prev_action, 1),
                                                    epsilon=self.settings.get_epsilon(self.frame_count),
                                                    choosing=True)
        return _, _, value.cpu().data.numpy().item(), self.hidden_state.cpu().data.numpy(), action
        
                                

    def _sample(self, agent_state):
        _, _, self.value, self.hidden_state, self.action = self._forward(agent_state, choosing=True)
        self.frame_count += 1
        self.step += 1
        return self.action
        
    def state_space_converter(self, state):
        return state_modifier.graph_conv_modifier(state)[:3]
    
    def action_space_converter(self, personal_action):
        return personal_action
        
    
    def train(self, run_settings):
        self.memory.compute_vtargets_adv(self.PPO_settings['discount_factor'],
                                            self.PPO_settings['lambda'])
                                            
        batch_size = run_settings.batch_size
        num_iters = int(len(self.memory) / batch_size)
        epochs = run_settings.num_epochs
        
        for i in range(epochs):
        
            pol_loss = 0
            vf_loss = 0
            ent_total = 0
        
            for j in range(num_iters):
                
                d_pol, d_vf, d_ent = self.train_step(batch_size)
                pol_loss += d_pol
                vf_loss += d_vf
                ent_total += d_ent
            
            self.epochs_trained += 1
            pol_loss /= num_iters
            vf_loss /= num_iters
            ent_total /= num_iters
            print("Epoch %d: Policy loss: %f. Value loss: %f. Entropy %f" % 
                            (self.epochs_trained, 
                            pol_loss, 
                            vf_loss, 
                            ent_total)
                            )
        self.update_target_net()
         
        print("\n\n ------- Training sequence ended ------- \n\n")
    
    
    def train_step(self, batch_size):
    
        hist_size = self.PPO_settings['hist_size']
        device = self.PPO_settings['device']
        eps_denom = self.PPO_settings['eps_denom']
        c1 = self.PPO_settings['c1']
        c2 = self.PPO_settings['c2']
        clip_param = self.PPO_settings['clip_param']
        
        
        mini_batch = self.memory.sample_mini_batch(self.frame_count,
                                                    hist_size)
        mini_batch = np.array(mini_batch).transpose()
        
        states = np.stack(mini_batch[0], axis=0)
        G_states = np.stack(states[:,0], axis=0)
        X_states = np.stack(states[:,1], axis=0)
        avail_states = np.stack(states[:,2], axis=0)
        hidden_states = np.concatenate(states[:,3], axis=2)
        prev_actions = np.stack(states[:,4], axis=0)
        relevant_states = np.stack(states[:,5], axis=0)
        
        n = states.shape[0]
                
        actions = np.array(list(mini_batch[1]))
        spatial_actions = np.stack(actions[:,0],0)
        first_spatials = spatial_actions[:,0]
        second_spatials = spatial_actions[:,1]
        nonspatial_acts = np.array(actions[:,1]).astype(np.int64)
        
        rewards = np.array(list(mini_batch[2]))
        dones = mini_batch[3]
        v_returns = mini_batch[5].astype(np.float32)
        advantages = mini_batch[6].astype(np.float32)
                
        first_spatials = torch.from_numpy(first_spatials).to(device)
        second_spatials = torch.from_numpy(second_spatials).to(device)
        nonspatial_acts = torch.from_numpy(nonspatial_acts).to(device)
        nonspatial_acts = nonspatial_acts.unsqueeze(1)
                
        rewards = torch.from_numpy(rewards).to(device)
        dones = torch.from_numpy(np.uint8(dones)).to(device)
        v_returns = torch.from_numpy(v_returns).to(device)
        advantages = torch.from_numpy(advantages).to(device)
                
        advantages = (advantages - advantages.mean()) 
        advantages = advantages / (torch.clamp(advantages.std(), eps_denom))
        
        spatial_probs, nonspatial_probs, values, _, _ = self.model(
                                                    G_states, 
                                                    X_states,
                                                    avail_states,
                                                    hidden_states,
                                                    prev_actions,
                                                    relevant_frames=relevant_states
                                                    )
                                                    
        old_spatial_probs, old_nonspatial_probs, old_values, _, _ = self.target_model(
                                                    G_states,
                                                    X_states,
                                                    avail_states,
                                                    hidden_states,
                                                    prev_actions,
                                                    relevant_frames=relevant_states
                                                    )
        
        gathered_nonspatials = nonspatial_probs.gather(1, nonspatial_acts).squeeze(1)
        old_gathered_nonspatials = old_nonspatial_probs.gather(1, nonspatial_acts).squeeze(1)
        
        first_spatial_mask = (nonspatial_acts < 3).to(device).float().squeeze(1)
        second_spatial_mask = (nonspatial_acts == 0).to(device).float().squeeze(1)
        
        numerator = torch.log(gathered_nonspatials + eps_denom)
        numerator = numerator + torch.log(self.index_spatial_probs(spatial_probs[:,0,:,:], first_spatials) + eps_denom) * first_spatial_mask 
        numerator = numerator + (torch.log(self.index_spatial_probs(spatial_probs[:,1,:,:], second_spatials) + eps_denom) * second_spatial_mask)
        
        denom = torch.log(old_gathered_nonspatials + eps_denom) 
        denom = denom + torch.log(self.index_spatial_probs(old_spatial_probs[:,0,:,:], first_spatials) + eps_denom) * first_spatial_mask 
        denom = denom + (torch.log(self.index_spatial_probs(old_spatial_probs[:,1,:,:], second_spatials) + eps_denom) * second_spatial_mask)
        denom = denom.detach()
        
        ratio = torch.exp(numerator - denom)
        ratio_adv = ratio * advantages.detach()
        bounded_adv = torch.clamp(ratio, 1-clip_param, 1+clip_param)
        bounded_adv = bounded_adv * advantages.detach()
        
        pol_avg = - ((torch.min(ratio_adv, bounded_adv)).mean())
        value_loss = self.loss(values.squeeze(1), v_returns.detach())
        ent = self.entropy(spatial_probs, nonspatial_probs)
        
        total_loss = pol_avg + c1 * value_loss - c2 * ent
        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()
        
        pol_loss = pol_avg.detach().item()
        vf_loss = value_loss.detach().item()
        ent_total = ent.detach().item() 
        
        return pol_loss, vf_loss, ent_total
        
    def load(self):
        self.net.load_state_dict(torch.load("save_model/Starcraft2" + self.env.map + "PPO"))
        self.update_target_net()
        
    def save(self):
        torch.save(self.model.state_dict(), "save_model/Starcraft2PPO")
        
    def push_memory(self, state, action, reward, done):
        push_state = list(state) + [self.prev_hidden_state]
        self.memory.push(push_state, action, reward, done, self.value, 0, 0, self.step)
        if done:
            step = 0
            value = 0
            self.hidden_state = self.model.init_hidden(use_torch=False)
        
        
    ### Unique PPO functions below this line
     
    def update_target_net(self):
        self.target_model.load_state_dict(self.model.state_dict())
     
    def index_spatial_probs(self, spatial_probs, indices):
        index_tuple = torch.meshgrid([torch.arange(x) for x in spatial_probs.size()[:-2]]) + (indices[:,0], indices[:,1],)
        output = spatial_probs[index_tuple]
        return output
        
    def entropy(self, spatial_probs, nonspatial_probs):
        c3 = self.PPO_settings['c3']
        c4 = self.PPO_settings['c4']
        eps_denom = self.PPO_settings['eps_denom']
        
        prod_s = spatial_probs[:,0,:,:] * torch.log(spatial_probs[:,0,:,:]+eps_denom)
        prod_n = nonspatial_probs * torch.log(nonspatial_probs+eps_denom)
        
        ent = - c3 * (torch.mean(torch.sum(prod_s, dim=(1,2))))
        ent = ent - c4 * torch.mean(torch.sum(prod_n, dim=1))
        
        return ent
        
        

settings_ppo = AgentSettings(
    optimizer=optim.Adam,
    learning_rate=0.00025,
    epsilon_max=1.0,
    epsilon_min=0.05,
    epsilon_duration=1000000)
