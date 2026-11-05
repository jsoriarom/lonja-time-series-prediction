"""Utilidades de preprocesado."""

import numpy as np
import pandas as pd


def uniform_ffill(
        data: pd.DataFrame,
        time_col: str = 'date',
        freq: str = '7D',
    ) -> pd.DataFrame:
    """
    Rellena huecos para que los registros estén separados por intervalos de tiempo uniformes (`freq`).
    Las filas nuevas toman el último valor conocido (forward fill).
    """
    df = data.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    return df.set_index(time_col).resample(freq).ffill().ffill().reset_index()


def to_log_retornos(precios: np.ndarray) -> np.ndarray:
    """
    Convierte una matriz de precios en retornos logarítmicos.
    La matriz resultante tiene 1 fila menos (la primera).
    """
    return np.diff(np.log(precios.astype(np.float64)), axis=0)


def to_precios(log_retornos: np.ndarray, precio_inicial: np.ndarray) -> np.ndarray:
    """
    Convierte una matriz de log-retornos de vuelta a precios reales.
    Requiere `precio_inicial`: (n_cols,) con el precio base de cada columna.
    """
    precio_inicial = np.asarray(precio_inicial, dtype=np.float64)
    precios = precio_inicial * np.exp(np.cumsum(log_retornos, axis=0, dtype=np.float64))
    return np.concatenate([precio_inicial[None, ...], precios], axis=0)