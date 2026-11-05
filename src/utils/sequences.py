"""Preparación de conjuntos de datos para modelos supervisados a partir
    de series temporales.

Genera ventanas deslizantes para modelos secuenciales (p. ej., LSTM, decoders)
y su versión aplanada para modelos tabulares (p. ej., random forest).
"""

import numpy as np


def to_dataset(
    data: np.ndarray,
    window_dim: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Divide la serie en ventanas deslizantes de `window_dim` filas.
    Devuelve `x` e `y`, donde cada fila de `y` es la fila siguiente a
    su ventana correspondiente.

    x: (n_records, window_dim, n_cols),
    y: (n_records, n_cols),
    con n_records = len(data) - window_dim.
    """

    x = np.asarray([
        data[i : i+window_dim, :]
        for i in range(len(data) - window_dim)
    ], dtype=np.float32)

    y = np.asarray(data[window_dim:, :], dtype=np.float32)

    return x, y


def flatten_dataset(x: np.ndarray) -> np.ndarray:
    """Aplana cada ventana en un vector: (n_records, window_dim * n_cols)."""

    return np.reshape(x, shape=(len(x), -1))