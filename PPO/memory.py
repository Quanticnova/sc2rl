from config import *
from collections import deque
import utils
import numpy as np
import random


class ReplayMemory(object):
    def __init__(self, mem_cap, hist_size, batch_size):
        self.memory = deque(maxlen=mem_cap)
        self.nonspatial_action_space = GraphConvConfigMinigames.action_space
        self.spatial_action_width = GraphConvConfigMinigames.spatial_width
        self.access_num = 0
        self.batch_size = batch_size
        self.reset_num = int(mem_cap / batch_size)
        self.indices = []
        self.Memory_capacity = mem_cap
        self.history_size = hist_size
        self.update_indices()
    
    def push(self, history, action, reward, done, vtarg, ret, adv, step):
        # history, action, reward, done, vtarg, adv
        self.memory.append([history, action, reward, done, vtarg, ret, adv, step])
        
        
    def update_indices(self):
        self.indices = list(range(1, self.Memory_capacity - (self.history_size-1)))
        random.shuffle(self.indices)

    def sample_mini_batch(self, frame, hist_size):
        
        
        mini_batch = []
        if frame >= self.Memory_capacity:
            sample_range = self.Memory_capacity
        else:
            sample_range = frame

        
            

        # history size
        
        lower = self.batch_size*self.access_num
        upper = min((self.batch_size*(self.access_num+1)), sample_range)

        idx_sample = self.indices[lower:upper]
        states = []
        for i in idx_sample:
            sample = []
            G_samp = []
            X_samp = []
            avail_samp = []
            hidden_samp = []
            prev_action_samp = []
            
            
            for j in range(self.history_size):
                sample.append(self.memory[i + j])
                #print("\n", self.memory[i+j], "\n")
                if (self.memory[i+j][-1] == 0):
                    for k in range(j):
                    
                        G_samp[i+k] = np.zeros(G_samp[i+k].shape)
                        X_samp[i+k] = np.zeros(X_samp[i+k].shape)
                        avail_samp[i+k] = np.zeros(avail_samp[i+k].shape)
                        hidden_samp[i+k] = np.zeros(hidden_samp[i+k].shape)
                    
                G_samp.append(self.memory[i+j][0][0])
                X_samp.append(self.memory[i+j][0][1])
                avail_samp.append(self.memory[i+j][0][2])
                hidden_samp.append(self.memory[i+j][0][3])
                
                action_arr = utils.action_to_onehot(self.memory[i+j][1], self.nonspatial_action_space, self.spatial_action_width)
                        
                prev_action_samp.append(action_arr)
                
                
            G_samp = np.array(G_samp)
            X_samp = np.array(X_samp)
            avail_samp = np.array(avail_samp)
            hidden_samp = np.array(hidden_samp)
            prev_action_samp = np.array(prev_action_samp)

            #sample = np.array(sample)
            row = sample[self.history_size-1]
            #print(row)
            #print(sample.shape, row.shape, sample[:,0].shape, sample[0,:].shape, sample[:,0][0].shape, sample[0].shape, type(sample[:,0]), type(sample[:,0][0]))
            row[0] = np.array([G_samp, X_samp, avail_samp, hidden_samp, prev_action_samp])
            mini_batch.append(row)


        self.access_num = (self.access_num + 1) % self.reset_num
        if (self.access_num == 0):
            self.update_indices()

        return mini_batch
        
    def compute_vtargets_adv(self, gamma, lam, frame_next_val):
        N = len(self)
        
        prev_gae_t = 0
       
        
        for i in reversed(range(N)):
            
            if i+1 == N:
                vnext = frame_next_val
                nonterminal = 1
            else:
                vnext = self.memory[i+1][4]
                nonterminal = 1 - self.memory[i+1][3]    # 1 - done
            delta = self.memory[i][2] + gamma * vnext * nonterminal - self.memory[i][4]
            gae_t = delta + gamma * lam * nonterminal * prev_gae_t
            self.memory[i][6] = gae_t    # advantage
            self.memory[i][5] = gae_t + self.memory[i][4]  # advantage + value
            prev_gae_t = gae_t
        

    def __len__(self):
        return len(self.memory)
