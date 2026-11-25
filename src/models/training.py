"""Training loop shared by all neural networks, so they are compared fairly."""

import copy
import time
from typing import Callable

import numpy as np
import torch
from torch import nn


def train_network(
    make_model: Callable[[], nn.Module],
    train_windows: np.ndarray,
    train_targets: np.ndarray,
    validation_windows: np.ndarray,
    validation_targets: np.ndarray,
    target_scale: float,
    seed: int = 0,
    max_epochs: int = 60,
    patience: int = 8,
    learning_rate: float = 1e-3,
    batch_size: int = 256,
) -> tuple[nn.Module, dict]:
    """Train one network with early stopping and return (best model, history).

    Targets are divided by `target_scale` (the RUL cap) so the network learns
    numbers between 0 and 1, which trains more steadily than 0 to 125.

    Early stopping: after every pass over the training data (an epoch) the
    model is checked on validation engines. Training stops once the validation
    error has not improved for `patience` epochs, and the best version is kept.
    This is why validation engines must never be used for anything else.
    """
    torch.manual_seed(seed)
    model = make_model()
    optimiser = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_function = nn.MSELoss()

    x_train = torch.from_numpy(train_windows)
    y_train = torch.from_numpy(train_targets / target_scale)
    x_validation = torch.from_numpy(validation_windows)
    y_validation = torch.from_numpy(validation_targets / target_scale)
    shuffle_generator = torch.Generator().manual_seed(seed)

    history = {"train_rmse": [], "validation_rmse": []}
    best_rmse, best_state, epochs_without_improvement = float("inf"), None, 0
    started = time.perf_counter()

    for _ in range(max_epochs):
        model.train()
        order = torch.randperm(len(x_train), generator=shuffle_generator)
        squared_error_sum = 0.0
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            optimiser.zero_grad()
            loss = loss_function(model(x_train[batch]), y_train[batch])
            loss.backward()
            # Recurrent networks occasionally produce very large gradients; limit them.
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimiser.step()
            squared_error_sum += loss.item() * len(batch)

        model.eval()
        with torch.no_grad():
            validation_loss = loss_function(model(x_validation), y_validation).item()
        history["train_rmse"].append(float(np.sqrt(squared_error_sum / len(x_train)) * target_scale))
        history["validation_rmse"].append(float(np.sqrt(validation_loss) * target_scale))

        if history["validation_rmse"][-1] < best_rmse - 1e-4:
            best_rmse = history["validation_rmse"][-1]
            best_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.load_state_dict(best_state)
    history["best_validation_rmse"] = best_rmse
    history["best_epoch"] = int(np.argmin(history["validation_rmse"])) + 1
    history["seconds"] = time.perf_counter() - started
    return model, history


def predict_rul(model: nn.Module, windows: np.ndarray, target_scale: float) -> np.ndarray:
    """Predict RUL in cycles, limited to the range the model was trained on."""
    model.eval()
    with torch.no_grad():
        predicted = model(torch.from_numpy(windows)).numpy() * target_scale
    return np.clip(predicted, 0, target_scale)
