"""Neural network architectures for RUL prediction from sensor windows.

Every network takes a batch of windows shaped (batch, cycles, channels) and
returns one number per window: the predicted RUL as a fraction of the RUL cap.
"""

import torch
from torch import nn


class MLPRegressor(nn.Module):
    """Fully connected network on the flattened window.

    It sees all cycles at once but has no built-in notion of their order:
    cycle 1 and cycle 30 are just different input positions.
    """

    def __init__(self, window: int, channels: int, hidden: int = 128, dropout: float = 0.2):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Flatten(),
            nn.Linear(window * channels, hidden), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        return self.layers(windows).squeeze(-1)


class RecurrentRegressor(nn.Module):
    """LSTM or GRU that reads the window one cycle at a time.

    The network keeps a running summary (its hidden state) and updates it with
    each new cycle. The summary after the last cycle is turned into the RUL.
    """

    def __init__(self, channels: int, cell: str = "lstm", hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        super().__init__()
        recurrent_class = {"lstm": nn.LSTM, "gru": nn.GRU}[cell]
        self.recurrent = recurrent_class(
            channels, hidden, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.head = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden // 2, 1))

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.recurrent(windows)
        return self.head(outputs[:, -1]).squeeze(-1)   # state after the most recent cycle


class _TemporalBlock(nn.Module):
    """Two dilated causal convolutions with a skip connection."""

    def __init__(self, in_channels: int, out_channels: int, kernel: int, dilation: int, dropout: float):
        super().__init__()
        # Padding on the left only, so an output never depends on later cycles.
        self.left_padding = (kernel - 1) * dilation
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel, dilation=dilation)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel, dilation=dilation)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.match_channels = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, signal: torch.Tensor) -> torch.Tensor:
        out = self.dropout(self.activation(self.conv1(nn.functional.pad(signal, (self.left_padding, 0)))))
        out = self.dropout(self.activation(self.conv2(nn.functional.pad(out, (self.left_padding, 0)))))
        return self.activation(out + self.match_channels(signal))


class TCNRegressor(nn.Module):
    """Temporal convolutional network.

    Slides small filters along the time axis. Each block doubles the spacing
    between the cycles a filter looks at (dilation 1, 2, 4, 8), so four blocks
    with kernel 3 cover 61 cycles, more than the 30-cycle window.
    """

    def __init__(self, channels: int, hidden: int = 32, kernel: int = 3, dilations=(1, 2, 4, 8), dropout: float = 0.2):
        super().__init__()
        blocks, in_channels = [], channels
        for dilation in dilations:
            blocks.append(_TemporalBlock(in_channels, hidden, kernel, dilation, dropout))
            in_channels = hidden
        self.blocks = nn.Sequential(*blocks)
        self.head = nn.Linear(hidden, 1)

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        features = self.blocks(windows.transpose(1, 2))   # Conv1d expects (batch, channels, cycles)
        return self.head(features[:, :, -1]).squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


class TransformerRegressor(nn.Module):
    """Small Transformer encoder.

    Each cycle is turned into a vector, a learned position marker is added so
    the network knows the order of the cycles, and attention layers let every
    cycle look at every other cycle. The representation of the most recent
    cycle is turned into the RUL.
    """

    def __init__(self, window: int, channels: int, width: int = 64, heads: int = 4, layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.embed = nn.Linear(channels, width)
        self.position = nn.Parameter(torch.zeros(1, window, width))
        nn.init.normal_(self.position, std=0.02)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=width, nhead=heads, dim_feedforward=2 * width, dropout=dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.head = nn.Sequential(nn.Linear(width, width // 2), nn.ReLU(), nn.Linear(width // 2, 1))

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(self.embed(windows) + self.position)
        return self.head(encoded[:, -1]).squeeze(-1)
