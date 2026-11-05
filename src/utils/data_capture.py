"""Extrae precios de bovinos de base de datos de MongoDB y los exporta a CSV.

Uso:
  python data_capture.py --whoami
  python data_capture.py --describe bbdd.tabla [bbdd.tabla...]
  python data_capture.py --export bbdd.tabla [min=N] [max=N] [--pivot]

Credenciales en .env: MONGO_USER, MONGO_PASSWORD, MONGO_CLUSTER.
"""

import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

USAGE = """Uso:
  python data_capture.py --whoami
  python data_capture.py --describe bbdd.tabla [bbdd.tabla...]
  python data_capture.py --export bbdd.tabla [min=N] [max=N] [--pivot]"""


def connect() -> MongoClient:
    """Crea un cliente de MongoDB con las credenciales de .env."""
    load_dotenv()
    user, password, cluster = [
        os.getenv(f'MONGO_{k}') or '' for k in ['USER', 'PASSWORD', 'CLUSTER']
    ]
    uri = f'mongodb+srv://{quote_plus(user)}:{quote_plus(password)}@{cluster}'
    return MongoClient(uri)


def whoami(client: MongoClient):
    """Muestra las bases de datos accesibles y los privilegios del usuario actual."""

    print('\nEsquemas y tablas visibles:')
    for db_name in client.list_database_names():
        if db_name in ('admin', 'local', 'config'):
            continue
        print(f'- Base de datos "{db_name}"')

    print('\nPermisos del usuario:')
    auth = client.admin.command('connectionStatus', showPrivileges=True).get('authInfo', {})
    for p in auth.get('authenticatedUserPrivileges', []):
        res = p.get('resource', {})
        db, col = res.get('db') or '*', res.get('collection') or '*'
        print(f'- {db}.{col}: {", ".join(sorted(p.get("actions", [])))}')


def describe(client: MongoClient, tables: list[str]):
    """Muestra los campos y tipos de cada tabla en `tables` ("bbdd.coleccion")."""

    for nom_t in tables:
        db_name, _, col_name = nom_t.partition('.')
        fields = defaultdict(set)

        try:
            for doc in client[db_name][col_name].find().limit(10):
                for key, value in doc.items():
                    type_name = type(value).__name__
                    if isinstance(value, dict):
                        type_name += f' ({", ".join(sorted(value))})'
                    fields[key].add(type_name)
        except OperationFailure:
            fields = {'Sin permisos': set()}

        print(f'\n{nom_t}')
        for key, types in (fields or {'Vacía o no existe': set()}).items():
            print(f'- {key}: {" | ".join(sorted(types))}'.rstrip(': '))


def get_prices(
    client: MongoClient,
    table: str,
    min_year: int | None = None,
    max_year: int | None = None,
    pivot: bool = False,
) -> pd.DataFrame:
    """Devuelve los precios de bovinos de `table` ordenados por fecha.

    `min_year` y `max_year` para indicar rango (años). Con `pivot`, una fila
    por fecha y una columna por sexo_peso_clase.
    """

    db_name, _, col_name = table.partition('.')

    query: dict[str, Any] = {'animal.type': 'bovine'}
    dates = {}
    if min_year is not None:
        dates['$gte'] = datetime(min_year, 1, 1)
    if max_year is not None:
        dates['$lt'] = datetime(max_year + 1, 1, 1)
    if dates:
        query['date.standard'] = dates

    rows = [
        {
            'date': d['date']['standard'].date(),
            'price': d['price'],
            'sex': d['animal']['sex'][0].upper(),
            'weight': d['animal']['weight'],
            'fatType': d['animal']['fatType'],
        }
        for d in client[db_name][col_name].find(query)
    ]

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if pivot:
        df['cat'] = df['sex'] + '_' + df['weight'] + '_' + df['fatType']
        df = df.pivot(index='date', columns='cat', values='price').rename_axis(columns=None).reset_index()

    return df.sort_values('date', ignore_index=True)


def export(client: MongoClient, table: str, options: list[str]):
    """Guarda `get_prices()` en <coleccion>.csv.

    Opciones: min=N y max=N (rango años) y --pivot (una fila por fecha
    y una columna de precio por sexo_peso_clase).
    """
    opts = {k: int(v) for k, v in (o.split('=') for o in options if '=' in o)}  # ['min=2018'] -> {'min': 2018}
    df = get_prices(
        client, table,
        opts.get('min'),
        opts.get('max'),
        '--pivot' in options
    )

    if df.empty:
        print('No hay registros con esos filtros')
        return

    df_name = table.partition('.')[2]
    df.to_csv(f'{df_name}.csv', index=False)
    print(f'{len(df)} filas exportadas a {df_name}.csv')


def main(client: MongoClient, action: str, options: list[str]):
    """Ejecuta comando indicado en la línea de comandos"""

    if action == '--whoami':
        whoami(client)
    elif action == '--describe' and options:
        describe(client, options)
    elif action == '--export' and options:
        export(client, options[0], options[1:])
    else:
        print(USAGE)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(USAGE)

    with connect() as client:
        client.admin.command('ping')
        print('Conexión establecida')
        main(client, sys.argv[1], sys.argv[2:])