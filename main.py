from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Type, TypeVar, Callable
from models import Transaction, MarketPrice, Player
from operations import GTAOnlineOperations
import csv
import os
from contextlib import asynccontextmanager

app = FastAPI(title="GTA Online Microtransactions API")

# Pydantic models for request/response validation
class TransactionModel(BaseModel):
    transaction_id: int
    player_id: str
    item: str
    amount: int
    date: str

class MarketPriceModel(BaseModel):
    item_id: int
    item_name: str
    price: int
    date: str

class PlayerModel(BaseModel):
    player_id: str
    username: str
    total_spent: int = 0

# Initialize operations
ops = GTAOnlineOperations()

# Determine the base directory (directory of main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Generic type for models
T = TypeVar('T')

# Centralized CSV handling
def load_csv_generic(
    filename: str,
    model_class: Type[T],
    add_method: Callable[[T], None],
    field_mappings: Dict[str, str],
    key_field: str,
    field_types: Dict[str, type]
) -> None:
    filepath = os.path.join(BASE_DIR, filename)
    print(f"[LOAD] Intentando cargar: {filepath}")
    print(f"[LOAD] Directorio de trabajo actual: {os.getcwd()}")

    if not os.path.exists(filepath):
        print(f"[LOAD] Error: '{filepath}' no encontrado. Creando archivo con encabezados.")
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=field_mappings.values())
                writer.writeheader()
            print(f"[LOAD] Archivo {filepath} creado con encabezados.")
        except Exception as e:
            print(f"[LOAD] Error al crear {filepath}: {str(e)}")
        return

    try:
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            raw_content = csvfile.read().strip()
            print(f"[LOAD] Contenido crudo de {filepath}:\n{raw_content}")
            if not raw_content:
                print(f"[LOAD] Advertencia: '{filepath}' está vacío. Iniciando con datos vacíos.")
                return
            csvfile.seek(0)
            reader = csv.DictReader(csvfile)
            expected_fields = list(field_mappings.values())
            print(f"[LOAD] Encabezados encontrados: {reader.fieldnames}")
            if not all(field in reader.fieldnames for field in expected_fields):
                print(f"[LOAD] Error: '{filepath}' no tiene las columnas esperadas: {expected_fields}. Encontradas: {reader.fieldnames}")
                return
            loaded_keys = set()
            for row_num, row in enumerate(reader, start=2):
                print(f"[LOAD] Procesando fila {row_num} en {filepath}: {row}")
                try:
                    kwargs = {
                        key: (int(row[field]) if field_types.get(field, str) == int else row[field].strip())
                        for key, field in field_mappings.items()
                        if row[field] or field_types.get(field) == str
                    }
                    obj = model_class(**kwargs)
                    key_value = row[field_mappings[key_field]]
                    if key_value in loaded_keys:
                        print(f"[LOAD] Advertencia: Duplicado encontrado para {key_field}={key_value} en fila {row_num}. Omitiendo.")
                        continue
                    loaded_keys.add(key_value)
                    add_method(obj)
                except (KeyError, ValueError) as e:
                    print(f"[LOAD] Error al procesar fila {row_num} en {filepath}: {row}. Detalle: {str(e)}")
                    continue
            loaded_count = len(loaded_keys)
            print(f"[LOAD] {filepath} cargado exitosamente. Total: {loaded_count}")
    except Exception as e:
        print(f"[LOAD] Error al cargar {filepath}: {str(e)}. Iniciando con datos vacíos.")

def save_csv_generic(
    filename: str,
    data: List[T],
    field_mappings: Dict[str, str],
    sort_key: Callable[[Dict[str, Any]], Any]
) -> None:
    filepath = os.path.join(BASE_DIR, filename)
    print(f"[SAVE] Guardando datos en: {filepath}")
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(field_mappings.values())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            data_dicts = [vars(item) for item in data]
            for row in sorted(data_dicts, key=sort_key):
                writer.writerow({field_mappings[k]: v for k, v in row.items()})
        print(f"[SAVE] Datos guardados en {filepath} exitosamente. Total: {len(data)}")
    except Exception as e:
        print(f"[SAVE] Error al guardar {filepath}: {str(e)}")

# Lifespan event handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Field mappings and types
    field_mappings_transactions = {
        'transaction_id': 'transaction_id',
        'player_id': 'player_id',
        'item': 'item',
        'amount': 'amount',
        'date': 'date'
    }
    field_mappings_market_prices = {
        'item_id': 'item_id',
        'item_name': 'item_name',
        'price': 'price',
        'date': 'date'
    }
    field_mappings_players = {
        'player_id': 'player_id',
        'username': 'username',
        'total_spent': 'total_spent'
    }
    field_types = {
        'transaction_id': int,
        'amount': int,
        'item_id': int,
        'price': int,
        'total_spent': int
    }

    # Load data at startup
    load_csv_generic("transactions.csv", Transaction, ops.add_transaction, field_mappings_transactions, 'transaction_id', field_types)
    load_csv_generic("market_prices.csv", MarketPrice, ops.add_market_price, field_mappings_market_prices, 'item_id', field_types)
    load_csv_generic("players.csv", Player, ops.add_player, field_mappings_players, 'player_id', field_types)

    yield  # Application runs here

    # Shutdown: Save all data
    save_csv_generic("transactions.csv", ops.get_all_transactions(), field_mappings_transactions, lambda x: x['transaction_id'])
    save_csv_generic("market_prices.csv", ops.get_all_market_prices(), field_mappings_market_prices, lambda x: (x['item_id'], x['date']))
    save_csv_generic("players.csv", ops.get_all_players(), field_mappings_players, lambda x: x['player_id'])
    print("[SHUTDOWN] Shutting down GTA Online Microtransactions API.")

app.lifespan = lifespan

# Debug endpoint to check loaded data
@app.get("/debug/data-counts")
async def get_data_counts():
    return {
        "transactions_count": len(ops.get_all_transactions()),
        "market_prices_count": len(ops.get_all_market_prices()),
        "players_count": len(ops.get_all_players())
    }

# Endpoints for Transactions
@app.post("/transactions/", response_model=TransactionModel)
async def add_transaction(transaction: TransactionModel):
    trans = Transaction(
        transaction_id=transaction.transaction_id,
        player_id=transaction.player_id,
        item=transaction.item,
        amount=transaction.amount,
        date=transaction.date
    )
    try:
        ops.add_transaction(trans)
        save_csv_generic("transactions.csv", ops.get_all_transactions(),
                        {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item', 'amount': 'amount', 'date': 'date'},
                        lambda x: x['transaction_id'])
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return transaction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/transactions/", response_model=List[TransactionModel])
async def get_all_transactions():
    transactions = ops.get_all_transactions()
    print(f"[GET] Returning {len(transactions)} transactions")
    return [TransactionModel(**vars(t)) for t in transactions]

@app.get("/transactions/{transaction_id}", response_model=TransactionModel)
async def get_transaction(transaction_id: int):
    trans = ops.get_transaction_by_id(transaction_id)
    if trans is None:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return TransactionModel(**vars(trans))

@app.put("/transactions/{transaction_id}", response_model=TransactionModel)
async def update_transaction(transaction_id: int, transaction: TransactionModel):
    trans = Transaction(
        transaction_id=transaction.transaction_id,
        player_id=transaction.player_id,
        item=transaction.item,
        amount=transaction.amount,
        date=transaction.date
    )
    try:
        updated = ops.update_transaction(transaction_id, trans)
        save_csv_generic("transactions.csv", ops.get_all_transactions(),
                        {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item', 'amount': 'amount', 'date': 'date'},
                        lambda x: x['transaction_id'])
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return TransactionModel(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int):
    try:
        ops.delete_transaction(transaction_id)
        save_csv_generic("transactions.csv", ops.get_all_transactions(),
                        {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item', 'amount': 'amount', 'date': 'date'},
                        lambda x: x['transaction_id'])
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return {"message": f"Transacción {transaction_id} eliminada"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Endpoints for Market Prices
@app.post("/market-prices/", response_model=MarketPriceModel)
async def add_market_price(market_price: MarketPriceModel):
    price = MarketPrice(
        item_id=market_price.item_id,
        item_name=market_price.item_name,
        price=market_price.price,
        date=market_price.date
    )
    try:
        ops.add_market_price(price)
        save_csv_generic("market_prices.csv", ops.get_all_market_prices(),
                        {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
                        lambda x: (x['item_id'], x['date']))
        return market_price
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/market-prices/", response_model=List[MarketPriceModel])
async def get_all_market_prices():
    market_prices = ops.get_all_market_prices()
    print(f"[GET] Returning {len(market_prices)} market prices")
    return [MarketPriceModel(**vars(p)) for p in market_prices]

@app.get("/market-prices/{item_id}/{date}", response_model=MarketPriceModel)
async def get_market_price(item_id: int, date: str):
    price = ops.get_market_price_by_item_and_date(item_id, date)
    if price is None:
        raise HTTPException(status_code=404, detail="Precio de mercado no encontrado")
    return MarketPriceModel(**vars(price))

@app.put("/market-prices/{item_id}/{date}", response_model=MarketPriceModel)
async def update_market_price(item_id: int, date: str, market_price: MarketPriceModel):
    price = MarketPrice(
        item_id=market_price.item_id,
        item_name=market_price.item_name,
        price=market_price.price,
        date=market_price.date
    )
    try:
        updated = ops.update_market_price(item_id, date, price)
        save_csv_generic("market_prices.csv", ops.get_all_market_prices(),
                        {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
                        lambda x: (x['item_id'], x['date']))
        return MarketPriceModel(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/market-prices/{item_id}/{date}")
async def delete_market_price(item_id: int, date: str):
    try:
        ops.delete_market_price(item_id, date)
        save_csv_generic("market_prices.csv", ops.get_all_market_prices(),
                        {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
                        lambda x: (x['item_id'], x['date']))
        return {"message": f"Precio de mercado para ítem {item_id} en {date} eliminado"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Endpoints for Players
@app.post("/players/", response_model=PlayerModel)
async def add_player(player: PlayerModel):
    ply = Player(
        player_id=player.player_id,
        username=player.username,
        total_spent=player.total_spent
    )
    try:
        ops.add_player(ply)
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return player
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/players/", response_model=List[PlayerModel])
async def get_all_players():
    players = ops.get_all_players()
    print(f"[GET] Returning {len(players)} players")
    return [PlayerModel(**vars(p)) for p in players]

@app.get("/players/{player_id}", response_model=PlayerModel)
async def get_player(player_id: str):
    player = ops.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return PlayerModel(**vars(player))

@app.put("/players/{player_id}", response_model=PlayerModel)
async def update_player(player_id: str, player: PlayerModel):
    ply = Player(
        player_id=player.player_id,
        username=player.username,
        total_spent=player.total_spent
    )
    try:
        updated = ops.update_player(player_id, ply)
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return PlayerModel(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/players/{player_id}")
async def delete_player(player_id: str):
    try:
        ops.delete_player(player_id)
        save_csv_generic("players.csv", ops.get_all_players(),
                        {'player_id': 'player_id', 'username': 'username', 'total_spent': 'total_spent'},
                        lambda x: x['player_id'])
        return {"message": f"Jugador {player_id} eliminado"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Analytical Endpoints
@app.get("/analytics/total-spending")
async def get_total_spending():
    return {"total_spending": ops.calculate_total_spending()}

@app.get("/analytics/average-transaction")
async def get_average_transaction():
    return {"average_transaction": ops.calculate_average_transaction()}

@app.get("/analytics/inflation-rate")
async def get_inflation_rate(item_id: int, start_date: str, end_date: str):
    rate = ops.calculate_inflation_rate(item_id, start_date, end_date)
    if rate is None:
        raise HTTPException(status_code=404, detail="Datos insuficientes para calcular la tasa de inflación")
    return {"inflation_rate": rate}