from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Type, TypeVar, Callable, Optional
from datetime import datetime
import csv
import os
import json
import shutil
from contextlib import asynccontextmanager
import random
import uvicorn

# Updated imports
from models import Transaction, MarketPrice, Player
from operations import GTAOnlineOperations, TransactionError

# Create FastAPI app with metadata for Swagger UI
app = FastAPI(
    title="GTA Online Microtransactions API",
    description="API for analyzing microtransactions in GTA Online from 2013 to 2025",
    version="2.0.0",
)


# Pydantic models for request/response validation
class TransactionBase(BaseModel):
    player_id: str
    item: str
    amount: int
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    transaction_type: str = "purchase"


class TransactionCreate(TransactionBase):
    transaction_id: int = Field(default=0)  # 0 means auto-generate ID


class TransactionResponse(TransactionBase):
    transaction_id: int

    class Config:
        from_attributes = True


class MarketPriceBase(BaseModel):
    item_id: int
    item_name: str
    price: int
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


class MarketPriceCreate(MarketPriceBase):
    pass


class MarketPriceResponse(MarketPriceBase):
    class Config:
        from_attributes = True


class PlayerBase(BaseModel):
    username: str
    balance: int = 0  # Will be randomly generated if left at 0


class PlayerCreate(PlayerBase):
    player_id: str


class PlayerResponse(PlayerBase):
    player_id: str
    total_spent: int = 0

    class Config:
        from_attributes = True


class PlayerBalanceUpdate(BaseModel):
    balance: int


class PlayerAnalytics(BaseModel):
    player_id: str
    username: str
    current_balance: int
    total_spent: int
    purchase_count: int
    sale_count: int
    avg_purchase: float
    avg_sale: float


class InflationAnalytics(BaseModel):
    item_id: int
    item_name: str
    start_date: str
    end_date: str
    start_price: Optional[int]
    end_price: Optional[int]
    inflation_rate: Optional[float]


# Initialize operations
ops = GTAOnlineOperations()

# Determine the base directory (directory of main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure data directory exists
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Generic type for models
T = TypeVar('T')


# Improved CSV handling with backup functionality
def load_csv_generic(
        filename: str,
        model_class: Type[T],
        add_method: Callable,
        field_mappings: Dict[str, str],
        key_field: str,
        field_types: Dict[str, type]
) -> None:
    """
    Load data from CSV file with improved error handling and logging

    Args:
        filename: CSV filename
        model_class: Class to instantiate for each row
        add_method: Method to add each instance
        field_mappings: Dict mapping model fields to CSV headers
        key_field: Unique identifier field
        field_types: Dict mapping fields to their types
    """
    filepath = os.path.join(DATA_DIR, filename)
    print(f"[LOAD] Loading data from: {filepath}")

    # Create file with headers if it doesn't exist
    if not os.path.exists(filepath):
        print(f"[LOAD] File '{filepath}' not found. Creating file with headers.")
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=field_mappings.values())
                writer.writeheader()
            print(f"[LOAD] File {filepath} created with headers.")
        except Exception as e:
            print(f"[LOAD] Error creating {filepath}: {str(e)}")
        return

    try:
        # Make a backup before loading
        backup_file = f"{filepath}.backup"
        try:
            shutil.copy2(filepath, backup_file)
            print(f"[LOAD] Backup created at {backup_file}")
        except Exception as e:
            print(f"[LOAD] Warning: Could not create backup: {str(e)}")

        # Read and process the CSV file
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            # Check if file is empty
            raw_content = csvfile.read().strip()
            if not raw_content:
                print(f"[LOAD] Warning: '{filepath}' is empty. Starting with empty data.")
                return

            # Reset file pointer and read with DictReader
            csvfile.seek(0)
            reader = csv.DictReader(csvfile)

            # Validate headers
            expected_fields = list(field_mappings.values())
            if not reader.fieldnames:
                print(f"[LOAD] Error: '{filepath}' has no headers.")
                return

            if not all(field in reader.fieldnames for field in expected_fields):
                print(
                    f"[LOAD] Error: '{filepath}' is missing expected columns. Expected: {expected_fields}, Found: {reader.fieldnames}")
                return

            # Process rows
            loaded_keys = set()
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Convert fields to proper types and strip whitespace from strings
                    kwargs = {}
                    for key, field in field_mappings.items():
                        if field not in row:
                            print(f"[LOAD] Warning: Field '{field}' missing in row {row_num}")
                            continue

                        value = row[field]
                        if not value and field_types.get(field) != str:
                            continue

                        if field_types.get(field) == int:
                            try:
                                kwargs[key] = int(value)
                            except ValueError:
                                print(f"[LOAD] Warning: Invalid integer '{value}' for field '{field}' in row {row_num}")
                                kwargs[key] = 0
                        else:
                            kwargs[key] = value.strip() if isinstance(value, str) else value

                    # Create object instance
                    obj = model_class(**kwargs)

                    # Check for duplicates
                    key_csv_field = field_mappings[key_field]
                    key_value = row[key_csv_field]
                    if key_value in loaded_keys:
                        print(
                            f"[LOAD] Warning: Duplicate found for {key_field}={key_value} in row {row_num}. Skipping.")
                        continue

                    # Add to operations
                    if model_class == Player:
                        add_method(obj, with_random_balance=False)  # Don't override existing balances
                    elif model_class == Transaction:
                        add_method(obj, validate_balance=False)  # Don't validate balance when loading
                    else:
                        add_method(obj)

                    loaded_keys.add(key_value)

                except (KeyError, ValueError, TransactionError) as e:
                    print(f"[LOAD] Error processing row {row_num} in {filepath}: {row}. Detail: {str(e)}")
                    continue

            # Print summary
            print(f"[LOAD] {filepath} loaded successfully. Loaded {len(loaded_keys)} items.")

    except Exception as e:
        print(f"[LOAD] Error loading {filepath}: {str(e)}. Starting with empty data.")


def save_csv_generic(
        filename: str,
        data: List[T],
        field_mappings: Dict[str, str],
        sort_key: Callable[[Dict[str, Any]], Any]
) -> None:
    """
    Save data to CSV file with improved error handling and backups

    Args:
        filename: CSV filename
        data: List of objects to save
        field_mappings: Dict mapping model fields to CSV headers
        sort_key: Function to sort rows
    """
    filepath = os.path.join(DATA_DIR, filename)
    print(f"[SAVE] Saving data to: {filepath}")

    try:
        # Make backup of existing file before overwriting
        if os.path.exists(filepath):
            backup_file = f"{filepath}.backup"
            try:
                shutil.copy2(filepath, backup_file)
                print(f"[SAVE] Backup created at {backup_file}")
            except Exception as e:
                print(f"[SAVE] Warning: Could not create backup: {str(e)}")

        # Create temp file first to avoid corruption
        temp_filepath = f"{filepath}.tmp"
        with open(temp_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(field_mappings.values())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Convert objects to dicts and write rows
            data_dicts = [vars(item) for item in data]
            for row in sorted(data_dicts, key=sort_key):
                try:
                    # Map fields to CSV columns
                    csv_row = {field_mappings[k]: v for k, v in row.items() if k in field_mappings}
                    writer.writerow(csv_row)
                except Exception as e:
                    print(f"[SAVE] Error writing row {row}: {str(e)}")

        # Rename temp file to target file
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_filepath, filepath)
        print(f"[SAVE] Data saved to {filepath} successfully. Total: {len(data)} items.")

    except Exception as e:
        print(f"[SAVE] Error saving {filepath}: {str(e)}")
        # Try to clean up temp file
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except:
                pass


# Lifespan event handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Starting GTA Online Microtransactions API")

    # Field mappings and types
    field_mappings_transactions = {
        'transaction_id': 'transaction_id',
        'player_id': 'player_id',
        'item': 'item',
        'amount': 'amount',
        'date': 'date',
        'transaction_type': 'transaction_type'
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
        'balance': 'balance',
        'total_spent': 'total_spent'
    }
    field_types = {
        'transaction_id': int,
        'amount': int,
        'item_id': int,
        'price': int,
        'total_spent': int,
        'balance': int
    }

    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load data at startup
    load_csv_generic(
        "players.csv", Player, ops.add_player,
        field_mappings_players, 'player_id', field_types
    )
    load_csv_generic(
        "transactions.csv", Transaction, ops.add_transaction,
        field_mappings_transactions, 'transaction_id', field_types
    )
    load_csv_generic(
        "market_prices.csv", MarketPrice, ops.add_market_price,
        field_mappings_market_prices, 'item_id', field_types
    )

    yield  # Application runs here

    # Shutdown: Save all data
    print("[SHUTDOWN] Saving data before shutdown...")
    save_csv_generic(
        "players.csv", ops.get_all_players(),
        field_mappings_players, lambda x: x['player_id']
    )
    save_csv_generic(
        "transactions.csv", ops.get_all_transactions(),
        field_mappings_transactions, lambda x: x['transaction_id']
    )
    save_csv_generic(
        "market_prices.csv", ops.get_all_market_prices(),
        field_mappings_market_prices, lambda x: (x['item_id'], x['date'])
    )
    print("[SHUTDOWN] Shutting down GTA Online Microtransactions API.")


app.lifespan = lifespan


# Debug endpoints
@app.get("/debug/data-counts")
async def get_data_counts():
    """Get counts of all data types for debugging"""
    return {
        "transactions_count": len(ops.get_all_transactions()),
        "market_prices_count": len(ops.get_all_market_prices()),
        "players_count": len(ops.get_all_players())
    }


@app.get("/debug/data-dir")
async def get_data_dir():
    """Get data directory information"""
    files = os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else []
    return {
        "data_dir": DATA_DIR,
        "exists": os.path.exists(DATA_DIR),
        "files": files,
        "working_dir": os.getcwd()
    }


# Endpoints for Transactions
@app.post("/transactions/", response_model=TransactionResponse, status_code=201)
async def add_transaction(transaction: TransactionCreate):
    """
    Add a new transaction

    If transaction_id is 0, a new ID will be auto-generated.
    """
    trans = Transaction(
        transaction_id=transaction.transaction_id,
        player_id=transaction.player_id,
        item=transaction.item,
        amount=transaction.amount,
        date=transaction.date,
        transaction_type=transaction.transaction_type
    )
    try:
        ops.add_transaction(trans)

        # Save changes to files
        save_csv_generic(
            "transactions.csv", ops.get_all_transactions(),
            {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item',
             'amount': 'amount', 'date': 'date', 'transaction_type': 'transaction_type'},
            lambda x: x['transaction_id']
        )
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        # Get the transaction from operations to get the auto-generated ID
        updated_trans = ops.get_transaction_by_id(trans.transaction_id)
        return TransactionResponse(**vars(updated_trans))
    except TransactionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/transactions/", response_model=List[TransactionResponse])
async def get_all_transactions(
        player_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = Query(100, gt=0)
):
    """
    Get transactions with optional filters

    Args:
        player_id: Filter by player ID
        transaction_type: Filter by transaction type (purchase/sale)
        start_date: Filter by start date (inclusive)
        end_date: Filter by end date (inclusive)
        limit: Maximum number of transactions to return
    """
    transactions = ops.get_all_transactions()

    # Apply filters
    if player_id:
        transactions = [t for t in transactions if t.player_id == player_id]
    if transaction_type:
        transactions = [t for t in transactions if t.transaction_type == transaction_type]
    if start_date:
        transactions = [t for t in transactions if t.date >= start_date]
    if end_date:
        transactions = [t for t in transactions if t.date <= end_date]

    # Sort by date (newest first) and ID
    transactions.sort(key=lambda t: (t.date, t.transaction_id), reverse=True)

    # Apply limit
    transactions = transactions[:limit]

    print(f"[GET] Returning {len(transactions)} transactions")
    return [TransactionResponse(**vars(t)) for t in transactions]


@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: int):
    """Get a transaction by ID"""
    trans = ops.get_transaction_by_id(transaction_id)
    if trans is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse(**vars(trans))


@app.put("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(transaction_id: int, transaction: TransactionCreate):
    """Update an existing transaction"""
    trans = Transaction(
        transaction_id=transaction_id,  # Override any ID in the request
        player_id=transaction.player_id,
        item=transaction.item,
        amount=transaction.amount,
        date=transaction.date,
        transaction_type=transaction.transaction_type
    )
    try:
        updated = ops.update_transaction(transaction_id, trans)

        # Save changes to files
        save_csv_generic(
            "transactions.csv", ops.get_all_transactions(),
            {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item',
             'amount': 'amount', 'date': 'date', 'transaction_type': 'transaction_type'},
            lambda x: x['transaction_id']
        )
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return TransactionResponse(**vars(updated))
    except TransactionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: int):
    """Delete a transaction"""
    try:
        ops.delete_transaction(transaction_id)

        # Save changes to files
        save_csv_generic(
            "transactions.csv", ops.get_all_transactions(),
            {'transaction_id': 'transaction_id', 'player_id': 'player_id', 'item': 'item',
             'amount': 'amount', 'date': 'date', 'transaction_type': 'transaction_type'},
            lambda x: x['transaction_id']
        )
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return {"message": f"Transaction {transaction_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Endpoints for Market Prices
@app.post("/market-prices/", response_model=MarketPriceResponse, status_code=201)
async def add_market_price(market_price: MarketPriceCreate):
    """Add a new market price"""
    price = MarketPrice(
        item_id=market_price.item_id,
        item_name=market_price.item_name,
        price=market_price.price,
        date=market_price.date
    )
    try:
        ops.add_market_price(price)

        # Save changes to file
        save_csv_generic(
            "market_prices.csv", ops.get_all_market_prices(),
            {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
            lambda x: (x['item_id'], x['date'])
        )

        return MarketPriceResponse(**vars(price))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/market-prices/", response_model=List[MarketPriceResponse])
async def get_all_market_prices(
        item_id: Optional[int] = None,
        item_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
):
    """
    Get market prices with optional filters

    Args:
        item_id: Filter by item ID
        item_name: Filter by item name (case-insensitive substring match)
        start_date: Filter by start date (inclusive)
        end_date: Filter by end date (inclusive)
    """
    market_prices = ops.get_all_market_prices()

    # Apply filters
    if item_id is not None:
        market_prices = [p for p in market_prices if p.item_id == item_id]
    if item_name:
        market_prices = [p for p in market_prices if item_name.lower() in p.item_name.lower()]
    if start_date:
        market_prices = [p for p in market_prices if p.date >= start_date]
    if end_date:
        market_prices = [p for p in market_prices if p.date <= end_date]

    # Sort by item_id and date
    market_prices.sort(key=lambda p: (p.item_id, p.date))

    print(f"[GET] Returning {len(market_prices)} market prices")
    return [MarketPriceResponse(**vars(p)) for p in market_prices]


@app.get("/market-prices/{item_id}/latest", response_model=MarketPriceResponse)
async def get_latest_market_price(item_id: int):
    """Get the latest market price for an item"""
    price = ops.get_latest_market_price(item_id)
    if price is None:
        raise HTTPException(status_code=404, detail="Market price not found")
    return MarketPriceResponse(**vars(price))


@app.get("/market-prices/{item_id}/{date}", response_model=MarketPriceResponse)
async def get_market_price(item_id: int, date: str):
    """Get market price for a specific item on a specific date"""
    price = ops.get_market_price_by_item_and_date(item_id, date)
    if price is None:
        raise HTTPException(status_code=404, detail="Market price not found")
    return MarketPriceResponse(**vars(price))


@app.put("/market-prices/{item_id}/{date}", response_model=MarketPriceResponse)
async def update_market_price(item_id: int, date: str, market_price: MarketPriceCreate):
    """Update a market price"""
    price = MarketPrice(
        item_id=market_price.item_id,
        item_name=market_price.item_name,
        price=market_price.price,
        date=market_price.date
    )
    try:
        updated = ops.update_market_price(item_id, date, price)

        # Save changes to file
        save_csv_generic(
            "market_prices.csv", ops.get_all_market_prices(),
            {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
            lambda x: (x['item_id'], x['date'])
        )

        return MarketPriceResponse(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/market-prices/{item_id}/{date}")
async def delete_market_price(item_id: int, date: str):
    """Delete a market price"""
    try:
        ops.delete_market_price(item_id, date)

        # Save changes to file
        save_csv_generic(
            "market_prices.csv", ops.get_all_market_prices(),
            {'item_id': 'item_id', 'item_name': 'item_name', 'price': 'price', 'date': 'date'},
            lambda x: (x['item_id'], x['date'])
        )

        return {"message": f"Market price for item {item_id} on {date} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Endpoints for Players
@app.post("/players/", response_model=PlayerResponse, status_code=201)
async def add_player(player: PlayerCreate):
    """
    Add a new player

    If balance is 0, a random balance between 100,000 and 10,000,000 will be generated.
    """
    ply = Player(
        player_id=player.player_id,
        username=player.username,
        balance=player.balance,
        total_spent=0
    )
    try:
        created_player = ops.add_player(ply)

        # Save changes to file
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return PlayerResponse(**vars(created_player))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/players/", response_model=List[PlayerResponse])
async def get_all_players(username: Optional[str] = None):
    """
    Get all players with optional filters

    Args:
        username: Filter by username (case-insensitive substring match)
    """
    players = ops.get_all_players()

    if username:
        players = [p for p in players if username.lower() in p.username.lower()]

    # Sort by total_spent (highest first)
    players.sort(key=lambda p: p.total_spent, reverse=True)

    print(f"[GET] Returning {len(players)} players")
    return [PlayerResponse(**vars(p)) for p in players]


@app.get("/players/{player_id}", response_model=PlayerResponse)
async def get_player(player_id: str):
    """Get player by ID"""
    player = ops.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerResponse(**vars(player))


@app.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(player_id: str, player: PlayerCreate):
    """Update a player"""
    ply = Player(
        player_id=player_id,  # Override any ID in the request
        username=player.username,
        balance=player.balance,
        total_spent=ops.get_player_by_id(player_id).total_spent if ops.get_player_by_id(player_id) else 0
    )
    try:
        updated = ops.update_player(player_id, ply)

        # Save changes to file
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return PlayerResponse(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/players/{player_id}/balance", response_model=PlayerResponse)
async def update_player_balance(player_id: str, balance_update: PlayerBalanceUpdate):
    """Update a player's balance"""
    player = ops.get_player_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    updated_player = Player(
        player_id=player.player_id,
        username=player.username,
        balance=balance_update.balance,
        total_spent=player.total_spent
    )

    try:
        updated = ops.update_player(player_id, updated_player)

        # Save changes to file
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return PlayerResponse(**vars(updated))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/players/{player_id}")
async def delete_player(player_id: str):
    """Delete a player"""
    try:
        ops.delete_player(player_id)

        # Save changes to file
        save_csv_generic(
            "players.csv", ops.get_all_players(),
            {'player_id': 'player_id', 'username': 'username', 'balance': 'balance', 'total_spent': 'total_spent'},
            lambda x: x['player_id']
        )

        return {"message": f"Player {player_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Analytical Endpoints
@app.get("/analytics/total-spending")
async def get_total_spending():
    """Get total spending across all transactions"""
    return {"total_spending": ops.calculate_total_spending()}


@app.get("/analytics/average-transaction")
async def get_average_transaction(transaction_type: Optional[str] = None):
    """
    Get average transaction amount

    Args:
        transaction_type: Optional filter by transaction type ("purchase" or "sale")
    """
    avg = ops.calculate_average_transaction(transaction_type)
    return {
        "average_transaction": avg,
        "transaction_type": transaction_type if transaction_type else "all"
    }


@app.get("/analytics/inflation-rate", response_model=InflationAnalytics)
async def get_inflation_rate(item_id: int, start_date: str, end_date: str):
    """Calculate inflation rate for a specific item between two dates"""
    rate = ops.calculate_inflation_rate(item_id, start_date, end_date)

    if rate is None:
        raise HTTPException(status_code=404, detail="Insufficient data to calculate inflation rate")

    # Get item name from a market price
    prices = ops.get_market_trends(item_id)
    item_name = prices[0].item_name if prices else "Unknown Item"

    # Get start and end prices
    start_price = next((p.price for p in prices if p.date >= start_date), None)
    end_price = next((p.price for p in reversed(prices) if p.date <= end_date), None)

    return {
        "item_id": item_id,
        "item_name": item_name,
        "start_date": start_date,
        "end_date": end_date,
        "start_price": start_price,
        "end_price": end_price,
        "inflation_rate": rate
    }


@app.get("/analytics/player/{player_id}", response_model=PlayerAnalytics)
async def get_player_analytics(player_id: str):
    """Get spending statistics for a specific player"""
    stats = ops.get_player_spending_stats(player_id)
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])
    return stats


@app.get("/analytics/top-spenders", response_model=List[PlayerResponse])
async def get_top_spenders(limit: int = Query(5, gt=0, le=100)):
    """Get top spending players"""
    top_players = ops.get_top_spenders(limit)
    return [PlayerResponse(**vars(p)) for p in top_players]


@app.get("/analytics/market-trends/{item_id}")
async def get_market_trends(item_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None):
    """Get market price trends for a specific item"""
    trends = ops.get_market_trends(item_id, from_date, to_date)
    if not trends:
        raise HTTPException(status_code=404, detail=f"No market data found for item {item_id}")

    return {
        "item_id": item_id,
        "item_name": trends[0].item_name if trends else "Unknown",
        "prices": [{"date": p.date, "price": p.price} for p in trends]
    }
@app.get("/")
async def root():
    return {"message": "¡Hola! La aplicación FastAPI está funcionando correctamente."}

if __name__ == "__main__":
    # Obtener el puerto del entorno (Render lo proporciona) o usar 8000 como predeterminado
    port = int(os.environ.get("PORT", 8000))
    # Iniciar el servidor uvicorn, vinculándolo a 0.0.0.0 para aceptar conexiones externas
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
