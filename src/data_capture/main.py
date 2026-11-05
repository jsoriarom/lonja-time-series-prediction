"""Extrae precios de bovinos de base de datos de MongoDB y los exporta a CSV.

Uso:
  python main.py --whoami
  python main.py --describe bbdd.tabla [bbdd.tabla...]
  python main.py --export bbdd.tabla [min=N] [max=N] [--pivot]

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
  python main.py --whoami
  python main.py --describe bbdd.tabla [bbdd.tabla...]
  python main.py --export bbdd.tabla [min=N] [max=N] [--pivot]"""


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


def export(client: MongoClient, table: str, options: list[str]):
    """Exporta los precios de bovinos de `table` a <coleccion>.csv.
    
    Opciones: min=N y max=N (rango años) y --pivot (una fila por fecha
    y una columna de precio por sexo_peso_clase).
    """

    opts = dict(o.split('=') for o in options if '=' in o)  # ['min=2018'] -> {'min': '2018'}
    pivot = '--pivot' in options
    db_name, _, col_name = table.partition('.')

    query: dict[str, Any] = {'animal.type': 'bovine'}
    dates = {}
    if 'min' in opts:
        dates['$gte'] = datetime(int(opts['min']), 1, 1)
    if 'max' in opts:
        dates['$lt'] = datetime(int(opts['max']) + 1, 1, 1)
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

    if not rows:
        print('No hay registros con esos filtros')
        return

    df = pd.DataFrame(rows)
    if pivot:
        df['cat'] = df['sex'] + '_' + df['weight'] + '_' + df['fatType']
        df = df.pivot(index='date', columns='cat', values='price').reset_index()

    df.sort_values('date').to_csv(f'{col_name}.csv', index=False)
    print(f'{len(df)} filas exportadas a {col_name}.csv')


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

    load_dotenv()

    user, password, cluster = [
        os.getenv(f'MONGO_{k}') or '' for k in ['USER', 'PASSWORD', 'CLUSTER']
    ]

    uri = f'mongodb+srv://{quote_plus(user)}:{quote_plus(password)}@{cluster}'

    with MongoClient(uri) as client:
        client.admin.command('ping')
        print('Conexión establecida')
        main(client, sys.argv[1], sys.argv[2:])