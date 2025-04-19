from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from models import Transaction, MarketPrice, Player
from operations import GTAOnlineOperations
import csv
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

# Lifespan event handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load CSV data
    try:
        with open("gta_online_data.csv", newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['type'] == 'Transaction':
                    trans = Transaction(
                        int(row['transaction_id']),
                        row['player_id'],
                        row['item'],
                        int(row['amount']),
                        row['date']
                    )
                    ops.add_transaction(trans)
                elif row['type'] == 'MarketPrice':
                    price = MarketPrice(
                        int(row['item_id']),
                        row['item_name'],
                        int(row['price']),
                        row['date']
                    )
                    ops.add_market_price(price)
                elif row['type'] == 'Player':
                    player = Player(
                        row['player_id'],
                        row['username'],
                        int(row['total_spent']) if row['total_spent'] else 0
                    )
                    ops.add_player(player)
        print("CSV data loaded successfully.")
    except FileNotFoundError:
        print("Error: 'gta_online_data.csv' not found. Starting with empty data.")
    except Exception as e:
        print(f"Error loading CSV data: {str(e)}. Starting with empty data.")

    yield  # Application runs here

    # Shutdown: Optional cleanup
    print("Shutting down GTA Online Microtransactions API.")

app.lifespan = lifespan

# Endpoints for Transactions
@app.post("/transactions/", response_model=TransactionModel)
async def add_transaction(transaction: TransactionModel):
    trans = Transaction(
        transaction.transaction_id,
        transaction.player_id,
        transaction.item,
        transaction.amount,
        transaction.date
    )
    try:
        ops.add_transaction(trans)
        return transaction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/transactions/", response_model=List[TransactionModel])
async def get_all_transactions():
    return [
        TransactionModel(
            transaction_id=t.transaction_id,
            player_id=t.player_id,
            item=t.item,
            amount=t.amount,
            date=t.date
        ) for t in ops.get_all_transactions()
    ]

@app.get("/transactions/{transaction_id}", response_model=TransactionModel)
async def get_transaction(transaction_id: int):
    trans = ops.get_transaction_by_id(transaction_id)
    if trans is None:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return TransactionModel(
        transaction_id=trans.transaction_id,
        player_id=trans.player_id,
        item=trans.item,
        amount=trans.amount,
        date=trans.date
    )

# Endpoints for Market Prices
@app.post("/market-prices/", response_model=MarketPriceModel)
async def add_market_price(market_price: MarketPriceModel):
    price = MarketPrice(
        market_price.item_id,
        market_price.item_name,
        market_price.price,
        market_price.date
    )
    try:
        ops.add_market_price(price)
        return market_price
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/market-prices/", response_model=List[MarketPriceModel])
async def get_all_market_prices():
    return [
        MarketPriceModel(
            item_id=p.item_id,
            item_name=p.item_name,
            price=p.price,
            date=p.date
        ) for p in ops.get_all_market_prices()
    ]

@app.get("/market-prices/{item_id}/{date}", response_model=MarketPriceModel)
async def get_market_price(item_id: int, date: str):
    price = ops.get_market_price_by_item_and_date(item_id, date)
    if price is None:
        raise HTTPException(status_code=404, detail="Precio de mercado no encontrado")
    return MarketPriceModel(
        item_id=price.item_id,
        item_name=price.item_name,
        price=price.price,
        date=price.date
    )

# Endpoints for Players
@app.post("/players/", response_model=PlayerModel)
async def add_player(player: PlayerModel):
    ply = Player(
        player.player_id,
        player.username,
        player.total_spent
    )
    try:
        ops.add_player(ply)
        return player
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/players/", response_model=List[PlayerModel])
async def get_all_players():
    return [
        PlayerModel(
            player_id=p.player_id,
            username=p.username,
            total_spent=p.total_spent
        ) for p in ops.get_all_players()
    ]

@app.get("/players/{player_id}", response_model=PlayerModel)
async def get_player(player_id: str):
    player = ops.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return PlayerModel(
        player_id=player.player_id,
        username=player.username,
        total_spent=player.total_spent
    )

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