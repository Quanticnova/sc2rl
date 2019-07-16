import torch
import torch.nn as nn
import torch.nn.functional as F


"""
    Convolutional implementation of LSTM.
    Check https://pytorch.org/docs/stable/nn.html#lstm to see reference information
"""
class ConvLSTM(nn.Module):
    def __init__(self, input_size, hidden_size):

        self.input_to_input = nn.Conv2d(input_size, hidden_size, kernel_size=3, stride=1, padding=1)
        self.hidden_to_input = nn.Conv2d(hidden_size, hidden_size, kernel_size=3, stride=1, padding=1)

        self.input_to_forget = nn.Conv2d(input_size, hidden_size, kernel_size=3, stride=1, padding=1)
        self.hidden_to_forget = nn.Conv2d(hidden_size, hidden_size, kernel_size=3, stride=1, padding=1)

        self.input_to_gate = nn.Conv2d(input_size, hidden_size, kernel_size=3, stride=1, padding=1)
        self.hidden_to_gate = nn.Conv2d(hidden_size, hidden_size, kernel_size=3, stride=1, padding=1)

        self.input_to_output = nn.Conv2d(input_size, hidden_size, kernel_size=3, stride=1, padding=1)
        self.hidden_to_output = nn.Conv2d(hidden_size, hidden_size, kernel_size=3, stride=1, padding=1)

    """
        input: torch tensor of shape (N, D, H, W)
        hidden_state: torch tensor of shape (N, 2, D, H, W)

        D is placeholder as usual
    """
    def forward(self, input, hidden_state):

        h_0 = hidden_state[:,0]
        c_0 = hidden_state[:,1]
        i = F.sigmoid(self.input_to_input(input) + self.hidden_to_input(h_0))
        f = F.sigmoid(self.input_to_forget(input) + self.hidden_to_forget(h_0))
        g = F.tanh(self.input_to_gate(input) + self.hidden_to_gate(h_0))
        o = F.sigmoid(self.input_to_output(input) + self.hidden_to_output(h_0))
        c_t = f * c_0 + i * g
        h_t = o * F.tanh(c_t)

        hidden_state_out = torch.cat([h_t.unsqueeze(1), c_t.unsqueeze(1)], dim=1)

        return o, hidden_state_out






class ResnetBlock(nn.Module):
    def __init__(self, num_features, num_layers):
        super(ResnetBlock, self).__init__()

        self.activation = nn.ReLU
        self.residuals = nn.Sequential()
        for i in range(num_layers):
            self.residuals.add_module(
                "residual" + str(i+1),
                nn.Sequential(
                    nn.Conv2d(num_features, num_features, 3, 1, padding=0)
                    self.activation()
                )
            )

    def forward(self, x):
        out = self.residuals(x):
        return x + out


class SelfAttentionBlock(nn.Module):

    def __init__(self, in_size, num_features):
        super(SelfAttentionBlock, self).__init__()

        self.in_size = in_size
        self.num_features = num_features

        self.QueryLayer = nn.Sequential(
            nn.Linear(in_size, num_features),
            nn.Tanh(),
            nn.InstanceNorm1d(num_features)
        )

        self.KeyLayer = nn.Sequential(
            nn.Linear(in_size, num_features),
            nn.Tanh(),
            nn.InstanceNorm1d(num_features)
        )

        self.ValueLayer = nn.Sequential(
            nn.Linear(in_size, num_features),
            nn.Tanh(),
            nn.InstanceNorm1d(num_features)
        )

        self.QueryNorm = nn.InstanceNorm1d(num_features)
        self.KeyNorm = nn.InstanceNorm1d(num_features)
        self.ValueNorm = nn.InstanceNorm1d(num_features)

    """
        Take in x of shape (N, H, W, D), perform attention calculations,
        return processed output of shape (N, H, W, num_features)
    """
    def forward(self, x):
        (N, H, W, D) = x.shape
        flattened = x.flatten(start_dim=1, end_dim=-2)

        Q = self.QueryNorm(self.QueryLayer(flattened))
        K = self.KeyNorm(self.KeyLayer(flattened))
        V = self.ValueNorm(self.ValueLayer(flattened))

        numerator = torch.matmul(Q, K.permute(0,2,1))
        scaled = numerator / (torch.sqrt(self.num_features))
        attention_weights = F.softmax(scaled)
        A = torch.matmul(attention_weights, V)
        A = A.reshape((N, H, W, -1))

        return A

class Downsampler(nn.Module):
    def __init__(self, net_config, input_features):
        super(Downsampler, self).__init__()

        self.block1 = nn.Sequential(
            nn.Conv2d(net_config[input_features]],
                net_config['down_conv_features'],
                kernel_size=(4,4),
                stride=2,
                padding=2),
            nn.ReLU(),

            ResnetBlock(net_config['down_conv_features'],
                            net_config['resnet_depth']),
            ResnetBlock(net_config['down_conv_features'],
                            net_config['resnet_depth'])
        )

        self.block2 = nn.Sequential(
            nn.Conv2d(net_config['down_conv_features']],
                2*net_config['down_conv_features'],
                kernel_size=(4,4),
                stride=2,
                padding=2),
            nn.ReLU(),

            ResnetBlock(2*net_config['down_conv_features'],
                            net_config['resnet_depth']),
            ResnetBlock(2*net_config['down_conv_features'],
                            net_config['resnet_depth'])
        )

        self.block3 = nn.Sequential(
            nn.Conv2d(2*net_config[input_features]],
                4*net_config['down_conv_features'],
                kernel_size=(4,4),
                stride=2,
                padding=2),
            nn.ReLU(),

            ResnetBlock(4*net_config['down_conv_features'],
                            net_config['resnet_depth']),
            ResnetBlock(4*net_config['down_conv_features'],
                            net_config['resnet_depth'])
        )

    def forward(self, input):
        h1 = self.block1(input)
        h2 = self.block2(h1)
        h3 = self.block3(h2)
        return h3

class SpatialUpsampler(nn.Module):
    def __init__(self, net_config):
        super(Upsampler, self).__init__()
        self.tconv1 = nn.Sequential(
            nn.ConvTranspose2d(
                net_config['up_features'],
                net_config['up_conv_features'],
                kernel_size=4,
                stride=2,
                padding=1
            ),
            nn.ReLU()
        )

        self.tconv2 = nn.Sequential(
            nn.ConvTranspose2d(
                net_config['up_conv_features'],
                int(0.5 * net_config['up_conv_features']),
                kernel_size=4,
                stride=2,
                padding=1
            ),
            nn.ReLU()
        )

        self.conv_out = nn.Conv2d(net_config['relational_spatial_depth'],
                                        net_config['spatial_action_depth'],
                                        kernel_size=1,
                                        stride=1,
                                        padding=1)

    def forward(self, x, action_embedding):
        h1 = self.tconv1(x)
        h2 = self.tconv2(h1)

        ### @TODO: Append action_embedding to h2

        return None
