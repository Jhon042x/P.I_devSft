from fastapi import FastAPI, HTTPException, Depends, Query, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Type, TypeVar, Callable, Optional, Tuple  # Asegúrate que Tuple y Any estén aquí
from datetime import datetime
import csv
import os
import json
import shutil
from contextlib import asynccontextmanager
import random
import uvicorn  # Solo para referencia, no es necesario para ejecutar
import base64  # Utilizado en algún punto para imágenes, si no se usa puede eliminarse
import traceback  # Importado para ver el traceback completo en la consola
import matplotlib.pyplot as plt  # Importa matplotlib
import io                       # Para manejar datos en memoria
import base64                   # Para codificar imágenes a base64

# Updated imports
from models import Transaction, MarketPrice, Player
from operations import GTAOnlineOperations, TransactionError

# --- Data File Paths ---
DATA_DIR = "data"
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.csv")
MARKET_PRICES_FILE = os.path.join(DATA_DIR, "market_prices.csv")
PLAYERS_FILE = os.path.join(DATA_DIR, "players.csv")
ITEM_IMAGES_FILE = os.path.join(DATA_DIR, "item_images.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs("static/images", exist_ok=True)  # Ensure images directory exists for uploads


# --- Helper functions for data loading/saving ---

def load_transactions(ops: 'GTAOnlineOperations'):
    print(f"DEBUG: Intentando cargar transacciones desde: {TRANSACTIONS_FILE}")
    if not os.path.exists(TRANSACTIONS_FILE):
        print(f"DEBUG: ¡ERROR! Archivo de transacciones NO ENCONTRADO en: {TRANSACTIONS_FILE}")
        return
    try:
        with open(TRANSACTIONS_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            print(f"DEBUG: Cabeceras del archivo transactions.csv: {reader.fieldnames}")
            rows_read = 0
            for row in reader:
                try:
                    transaction_id = int(row['transaction_id'])
                    player_id = row['player_id']
                    item = row['item']
                    amount = int(row['amount'])
                    date = row['date']
                    transaction_type = row.get('transaction_type', 'purchase') # Default a 'purchase' si no existe
                    transaction = Transaction(
                        transaction_id=transaction_id,
                        player_id=player_id,
                        item=item,
                        amount=amount,
                        date=date,
                        transaction_type=transaction_type
                    )
                    ops.transactions[transaction_id] = transaction
                    ops._next_transaction_id = max(ops._next_transaction_id, transaction_id + 1)
                    rows_read += 1
                except (ValueError, KeyError) as e:
                    print(f"DEBUG: ERROR al leer fila de transacción: {row} - {e}")
            print(f"DEBUG: Se leyeron {rows_read} filas de transactions.csv")
    except Exception as e:
        print(f"DEBUG: ERROR general al abrir/leer transactions.csv: {e}")


def save_transactions(transactions: Dict[int, Transaction]):
    if not transactions:
        # If no transactions, ensure file is empty or just create header
        with open(TRANSACTIONS_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['transaction_id', 'player_id', 'item', 'amount', 'date', 'transaction_type'])
        return

    with open(TRANSACTIONS_FILE, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['transaction_id', 'player_id', 'item', 'amount', 'date', 'transaction_type']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for transaction in transactions.values():
            writer.writerow({
                'transaction_id': transaction.transaction_id,
                'player_id': transaction.player_id,
                'item': transaction.item,
                'amount': transaction.amount,
                'date': transaction.date,
                'transaction_type': transaction.transaction_type
            })


def load_market_prices(ops: 'GTAOnlineOperations'):
    print(f"DEBUG: Intentando cargar precios de mercado desde: {MARKET_PRICES_FILE}")
    if not os.path.exists(MARKET_PRICES_FILE):
        print(f"DEBUG: ¡ERROR! Archivo de precios de mercado NO ENCONTRADO en: {MARKET_PRICES_FILE}")
        return
    try:
        with open(MARKET_PRICES_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            print(f"DEBUG: Cabeceras del archivo market_prices.csv: {reader.fieldnames}")
            rows_read = 0
            for row in reader:
                try:
                    item_id = int(row['item_id'])
                    item_name = row['item_name']
                    price = int(row['price'])
                    date = row['date']
                    market_price = MarketPrice(item_id=item_id, item_name=item_name, price=price, date=date)
                    ops.market_prices[(item_id, date)] = market_price
                    rows_read += 1
                except (ValueError, KeyError) as e:
                    print(f"DEBUG: ERROR al leer fila de precio de mercado: {row} - {e}")
            print(f"DEBUG: Se leyeron {rows_read} filas de market_prices.csv")
    except Exception as e:
        print(f"DEBUG: ERROR general al abrir/leer market_prices.csv: {e}")


def save_market_prices(market_prices: Dict[Tuple[int, str], MarketPrice]):
    if not market_prices:
        with open(MARKET_PRICES_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['item_id', 'item_name', 'price', 'date'])
        return

    with open(MARKET_PRICES_FILE, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['item_id', 'item_name', 'price', 'date']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for market_price in market_prices.values():
            writer.writerow({
                'item_id': market_price.item_id,
                'item_name': market_price.item_name,
                'price': market_price.price,
                'date': market_price.date
            })


def load_players(ops: 'GTAOnlineOperations'):
    print(f"DEBUG: Intentando cargar jugadores desde: {PLAYERS_FILE}")
    if not os.path.exists(PLAYERS_FILE):
        print(f"DEBUG: ¡ERROR! Archivo de jugadores NO ENCONTRADO en: {PLAYERS_FILE}")
        return
    try:
        with open(PLAYERS_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            print(f"DEBUG: Cabeceras del archivo players.csv: {reader.fieldnames}")
            rows_read = 0
            for row in reader:
                try:
                    player_id = row['player_id']
                    username = row['username']
                    balance = int(row.get('balance', 0)) # Usar .get para valor por defecto si no existe
                    total_spent = int(row.get('total_spent', 0)) # Usar .get
                    player = Player(
                        player_id=player_id,
                        username=username,
                        balance=balance,
                        total_spent=total_spent
                    )
                    ops.players[player_id] = player
                    rows_read += 1
                except (ValueError, KeyError) as e:
                    print(f"DEBUG: ERROR al leer fila de jugador: {row} - {e}")
            print(f"DEBUG: Se leyeron {rows_read} filas de players.csv")
    except Exception as e:
        print(f"DEBUG: ERROR general al abrir/leer players.csv: {e}")


def save_players(players: Dict[str, Player]):
    if not players:
        with open(PLAYERS_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['player_id', 'username', 'balance', 'total_spent'])
        return

    with open(PLAYERS_FILE, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['player_id', 'username', 'balance', 'total_spent']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for player in players.values():
            writer.writerow({
                'player_id': player.player_id,
                'username': player.username,
                'balance': player.balance,
                'total_spent': player.total_spent
            })


def load_item_images(ops: 'GTAOnlineOperations'):
    print(f"DEBUG: Intentando cargar imágenes de ítems desde: {ITEM_IMAGES_FILE}")
    if not os.path.exists(ITEM_IMAGES_FILE):
        print(f"DEBUG: ¡ERROR! Archivo de imágenes de ítems NO ENCONTRADO en: {ITEM_IMAGES_FILE}")
        # Crea un archivo JSON vacío si no existe para evitar errores futuros
        with open(ITEM_IMAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"DEBUG: Creado archivo vacío para item_images.json")
        return
    try:
        with open(ITEM_IMAGES_FILE, 'r', encoding='utf-8') as f:
            ops.item_images = json.load(f)
        print(f"DEBUG: Se cargaron {len(ops.item_images)} entradas de item_images.json")
    except json.JSONDecodeError as e:
        print(f"DEBUG: ERROR al decodificar JSON de item_images.json: {e}. El archivo podría estar mal formado.")
        ops.item_images = {} # Reinicia a vacío para evitar problemas
    except Exception as e:
        print(f"DEBUG: ERROR general al abrir/leer item_images.json: {e}")

def load_all_data(ops: 'GTAOnlineOperations'):
    print("DEBUG: Iniciando carga de TODOS los datos...")
    load_transactions(ops)
    load_players(ops)
    load_market_prices(ops)
    load_item_images(ops)
    print("DEBUG: Finalizada carga de TODOS los datos.")

def save_item_images(item_images: Dict[str, str]):
    with open(ITEM_IMAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(item_images, f, indent=4)

# --- Initialize GTAOnlineOperations ---
ops = GTAOnlineOperations()
# --- FastAPI App Initialization ---
app = FastAPI(
    title="GTA Online Microtransactions API",
    description="API for analyzing microtransactions in GTA Online from 2013 to 2025",
    version="2.0.0",
)

# --- Jinja2 Templates and Static Files Setup ---
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- App Lifespan (Load/Save Data) ---
@app.on_event("startup")
async def startup_event():
    global ops
    print("DEBUG: Iniciando evento de startup...")
    load_all_data(ops)
    print(f"DEBUG: Después de cargar datos. Número de transacciones: {len(ops.transactions)}")
    print(f"DEBUG: Después de cargar datos. Número de jugadores: {len(ops.players)}")
    print(f"DEBUG: Después de cargar datos. Número de precios de mercado: {len(ops.market_prices)}") # <-- IMPORTANTE
    print(f"DEBUG: Después de cargar datos. Número de imágenes de ítems: {len(ops.item_images)}")
    # Opcional: imprimir el contenido de ops.market_prices para verificar
    # print(f"DEBUG: Contenido de ops.market_prices: {ops.market_prices}")



@app.on_event("shutdown")
async def shutdown_event():
    print("Guardando datos al cerrar la aplicación...")
    save_transactions(ops.transactions)
    save_market_prices(ops.market_prices)
    save_players(ops.players)
    save_item_images(ops.item_images)  # Save item images on shutdown
    print("Datos guardados. Aplicación apagada.")


# --- Pydantic Models for API (Request/Response schemas) ---
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
        from_attributes = True  # For Pydantic v2+


class MarketPriceBase(BaseModel):
    item_id: int
    item_name: str
    price: int
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


class MarketPriceCreate(MarketPriceBase):
    pass  # No extra fields for creation based on base


class MarketPriceResponse(MarketPriceBase):
    pass  # No extra fields for response based on base


class PlayerResponse(BaseModel):
    player_id: str
    username: str
    balance: int
    total_spent: int

    class Config:
        from_attributes = True  # For Pydantic v2+


# --- HTML Endpoints for Navigation and Forms ---

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serves the home page."""
    return templates.TemplateResponse("index.html", {"request": request})


# --- Market Item CRUD ---
@app.get("/add-item", response_class=HTMLResponse)
async def add_item_form(request: Request):
    """Renders the form to add a new market item."""
    return templates.TemplateResponse("add_item.html", {"request": request})


@app.post("/items", response_class=HTMLResponse)
async def create_market_item(
        request: Request,
        item_name: str = Form(...),
        price: int = Form(...),
        item_id: Optional[int] = Form(None),  # Allow user to provide ID or generate new
        image: Optional[UploadFile] = File(None)
):
    """Handles submission of the add item form, creates and saves a new market item."""
    try:
        new_item_id = item_id if item_id is not None and item_id > 0 else ops._get_next_market_item_id()
        current_date = datetime.now().strftime("%Y-%m-%d")

        image_filename = 'default.png'
        if image and image.filename:
            static_images_path = "static/images"
            os.makedirs(static_images_path, exist_ok=True)

            extension = os.path.splitext(image.filename)[1]
            image_filename = f"{new_item_id}_{datetime.now().timestamp()}{extension}"
            image_path = os.path.join(static_images_path, image_filename)
            with open(image_path, "wb") as f:
                content = await image.read()
                f.write(content)
            ops.item_images[str(new_item_id)] = image_filename  # Store filename mapped to item_id

        market_price = MarketPrice(
            item_id=new_item_id,
            item_name=item_name,
            price=price,
            date=current_date
        )
        ops.add_market_price(market_price)
        save_item_images(ops.item_images)  # Save image mappings
        return RedirectResponse(url="/view-items", status_code=303)
    except Exception as e:
        print(f"Error creating market item: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("add_item.html",
                                          {"request": request, "error": str(e), "item_name": item_name, "price": price,
                                           "item_id": item_id})


@app.get("/view-items", response_class=HTMLResponse)
async def view_items_page(request: Request, query: Optional[str] = None, query_type: Optional[str] = None):
    """Renders the page to view all market items with search functionality."""
    try:  # <--- Added try-except block
        items_to_display = []
        all_latest_prices = {}

        # Pre-process all latest prices for unique items
        for (item_id, date), price_obj in ops.market_prices.items():
            if item_id not in all_latest_prices or date > all_latest_prices[item_id].date:
                all_latest_prices[item_id] = price_obj

        if query and query_type:
            if query_type == "id" and query.isdigit():
                item_id_int = int(query)
                item = all_latest_prices.get(item_id_int)
                if item:
                    items_to_display.append(item)
            elif query_type == "name":
                for item_obj in all_latest_prices.values():
                    if query.lower() in item_obj.item_name.lower():
                        items_to_display.append(item_obj)
        else:
            items_to_display = list(all_latest_prices.values())

        items_with_images = []
        for item in items_to_display:
            image_filename = ops.item_images.get(str(item.item_id), 'default.png')
            items_with_images.append({
                "item_id": item.item_id,
                "item_name": item.item_name,
                "price": item.price,
                "date": item.date,
                "image_filename": image_filename
            })

        return templates.TemplateResponse("view_items.html",
                                          {"request": request, "items": items_with_images, "query": query,
                                           "query_type": query_type})

    except Exception as e:  # <--- Added try-except block
        print(f"Error in view_items_page: {e}")
        traceback.print_exc()  # Print full traceback
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.get("/edit-item/{item_id}", response_class=HTMLResponse)
async def edit_item_form(request: Request, item_id: int):
    """Renders the form to edit an existing market item."""
    try:  # <--- Added try-except block
        item_to_edit = ops.get_latest_market_price(item_id)
        if not item_to_edit:
            raise HTTPException(status_code=404, detail="Item not found")

        image_filename = ops.item_images.get(str(item_id), 'default.png')
        return templates.TemplateResponse("edit_item.html",
                                          {"request": request, "item": item_to_edit, "image_filename": image_filename})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in edit_item_form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.post("/items/update/{item_id}", response_class=HTMLResponse)
async def update_market_item(
        request: Request,
        item_id: int,
        item_name: str = Form(...),
        price: int = Form(...),
        image: Optional[UploadFile] = File(None)
):
    """Handles submission of the edit item form, updates an existing market item."""
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")

        latest_price_obj = ops.get_latest_market_price(item_id)
        if latest_price_obj and latest_price_obj.date == current_date:
            ops.update_market_price(item_id, current_date, new_price=price, new_item_name=item_name)
        else:
            new_price_entry = MarketPrice(
                item_id=item_id,
                item_name=item_name,
                price=price,
                date=current_date
            )
            ops.add_market_price(new_price_entry)

        if image and image.filename:
            static_images_path = "static/images"
            os.makedirs(static_images_path, exist_ok=True)

            old_image_filename = ops.item_images.get(str(item_id))
            if old_image_filename and old_image_filename != 'default.png':
                old_image_path = os.path.join(static_images_path, old_image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

            extension = os.path.splitext(image.filename)[1]
            image_filename = f"{item_id}_{datetime.now().timestamp()}{extension}"
            image_path = os.path.join(static_images_path, image_filename)
            with open(image_path, "wb") as f:
                content = await image.read()
                f.write(content)
            ops.item_images[str(item_id)] = image_filename

        save_item_images(ops.item_images)
        return RedirectResponse(url="/view-items", status_code=303)
    except Exception as e:
        print(f"Error updating market item: {e}")
        traceback.print_exc()
        item_to_edit = ops.get_latest_market_price(item_id)
        image_filename = ops.item_images.get(str(item_id), 'default.png')
        return templates.TemplateResponse("edit_item.html", {"request": request, "error": str(e), "item": item_to_edit,
                                                             "image_filename": image_filename})


@app.post("/items/delete/{item_id}", response_class=HTMLResponse)
async def delete_market_item(request: Request, item_id: int):
    """Deletes an item and all its historical prices."""
    try:
        ops.delete_market_item_history(item_id)
        return RedirectResponse(url="/view-items", status_code=303)
    except ValueError as e:
        print(f"Error deleting market item: {e}")
        traceback.print_exc()
        items_to_display = list(ops.get_all_market_prices())
        return templates.TemplateResponse("view_items.html",
                                          {"request": request, "error": str(e), "items": items_to_display})


# --- Player CRUD Endpoints ---
@app.get("/add-player", response_class=HTMLResponse)
async def add_player_form(request: Request):
    """Renders the form to add a new player."""
    try:  # <--- Added try-except block
        return templates.TemplateResponse("add_player.html", {"request": request})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in add_player_form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.post("/players", response_class=HTMLResponse)
async def create_player(
        request: Request,
        player_id: str = Form(...),
        username: str = Form(...),
        balance: int = Form(...)
):
    """Handles submission of the add player form, creates and saves a new player."""
    try:
        new_player = Player(player_id=player_id, username=username, balance=balance)
        ops.add_player(new_player)
        return RedirectResponse(url="/view-players", status_code=303)
    except ValueError as e:
        print(f"Error creating player: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("add_player.html",
                                          {"request": request, "error": str(e), "player_id": player_id,
                                           "username": username, "balance": balance})


@app.get("/view-players", response_class=HTMLResponse)
async def view_players_page(request: Request, query: Optional[str] = None):
    """Renders the page to view all players with search functionality."""
    try:  # <--- Added try-except block
        players_to_display = []
        if query:
            player = ops.get_player(query)
            if player:
                players_to_display.append(player)
        else:
            players_to_display = list(ops.players.values())
        return templates.TemplateResponse("view_players.html",
                                          {"request": request, "players": players_to_display, "query": query})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in view_players_page: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.get("/edit-player/{player_id}", response_class=HTMLResponse)
async def edit_player_form(request: Request, player_id: str):
    """Renders the form to edit an existing player."""
    try:  # <--- Added try-except block
        player_to_edit = ops.get_player(player_id)
        if not player_to_edit:
            raise HTTPException(status_code=404, detail="Player not found")
        return templates.TemplateResponse("edit_player.html", {"request": request, "player": player_to_edit})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in edit_player_form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.post("/players/update/{player_id}", response_class=HTMLResponse)
async def update_player(
        request: Request,
        player_id: str,
        username: str = Form(...),
        balance: int = Form(...)
):
    """Handles submission of the edit player form, updates an existing player."""
    try:
        ops.update_player_info(player_id, username=username, balance=balance)
        return RedirectResponse(url="/view-players", status_code=303)
    except ValueError as e:
        print(f"Error updating player: {e}")
        traceback.print_exc()
        player_to_edit = ops.get_player(player_id)  # Re-fetch to pre-fill form in case of error
        return templates.TemplateResponse("edit_player.html",
                                          {"request": request, "player": player_to_edit, "error": str(e)})


@app.post("/players/delete/{player_id}", response_class=HTMLResponse)
async def delete_player(request: Request, player_id: str):
    """Deletes a player and all their associated transactions."""
    try:
        ops.delete_player(player_id)
        return RedirectResponse(url="/view-players", status_code=303)
    except ValueError as e:
        print(f"Error deleting player: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("view_players.html",
                                          {"request": request, "error": str(e), "players": list(ops.players.values())})


# --- Transaction CRUD Endpoints ---
@app.get("/add-transaction", response_class=HTMLResponse)
async def add_transaction_form(request: Request):
    """Renders the form to add a new transaction."""
    try:  # <--- Added try-except block
        players = list(ops.players.values())  # Need list of players for dropdown
        # Get unique item names from market_prices for the dropdown
        items = sorted(list(set([(item.item_id, item.item_name) for item in ops.market_prices.values()])),
                       key=lambda x: x[1])
        return templates.TemplateResponse("add_transaction.html",
                                          {"request": request, "players": players, "items": items})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in add_transaction_form: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.post("/transactions", response_class=HTMLResponse)
async def create_transaction_html(
        request: Request,
        player_id: str = Form(...),
        item: str = Form(...),  # Item name from dropdown
        amount: int = Form(...),
        transaction_type: str = Form("purchase")
):
    """Handles submission of the add transaction form, creates and saves a new transaction."""
    try:
        new_transaction = Transaction(
            transaction_id=0,  # Will be auto-generated
            player_id=player_id,
            item=item,
            amount=amount,
            date=datetime.now().strftime("%Y-%m-%d"),
            transaction_type=transaction_type
        )
        ops.add_transaction(new_transaction)
        return RedirectResponse(url="/view-transactions", status_code=303)
    except (ValueError, TransactionError) as e:
        print(f"Error creating transaction: {e}")
        traceback.print_exc()
        players = list(ops.players.values())
        items = sorted(list(set([(item_obj.item_id, item_obj.item_name) for item_obj in ops.market_prices.values()])),
                       key=lambda x: x[1])
        return templates.TemplateResponse("add_transaction.html", {
            "request": request,
            "error": str(e),
            "player_id": player_id,
            "item": item,
            "amount": amount,
            "transaction_type": transaction_type,
            "players": players,
            "items": items
        })


@app.get("/view-transactions", response_class=HTMLResponse)
async def view_transactions_page(request: Request, player_id: Optional[str] = None):
    """Renders the page to view all transactions, with optional filtering by player."""
    try:  # <--- Added try-except block
        transactions_to_display = []
        if player_id:
            transactions_to_display = ops.get_player_transactions(player_id)
        else:
            transactions_to_display = list(ops.transactions.values())

        # Sort transactions by date (most recent first) and then by ID
        transactions_to_display.sort(key=lambda t: (t.date, t.transaction_id), reverse=True)

        players = list(ops.players.values())  # Needed for player filter dropdown
        return templates.TemplateResponse("view_transactions.html",
                                          {"request": request, "transactions": transactions_to_display,
                                           "player_id": player_id, "players": players})
    except Exception as e:  # <--- Added try-except block
        print(f"Error in view_transactions_page: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


@app.post("/transactions/delete/{transaction_id}", response_class=HTMLResponse)
async def delete_transaction_html(request: Request, transaction_id: int):
    """Deletes a transaction and attempts to revert player balance."""
    try:
        ops.delete_transaction(transaction_id)
        return RedirectResponse(url="/view-transactions", status_code=303)
    except TransactionError as e:
        print(f"Error deleting transaction: {e}")
        traceback.print_exc()
        transactions_to_display = list(ops.transactions.values())
        players = list(ops.players.values())
        return templates.TemplateResponse("view_transactions.html",
                                          {"request": request, "error": str(e), "transactions": transactions_to_display,
                                           "players": players})


# --- Analytics Endpoints ---
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    try:
        total_transactions = len(ops.transactions)
        total_players = len(ops.players)
        total_items = len({item.item_id for item in ops.market_prices.values()})  # Count unique item_ids

        # Calculate total spent from players' total_spent attribute (updated by purchases)
        total_spent_gta_dollars = sum(player.total_spent for player in ops.players.values())

        # Top Spenders
        top_spenders = ops.get_top_spenders(5)

        # Top Most Expensive Items (latest price)
        latest_prices = {}
        for (item_id, date), price_obj in ops.market_prices.items():
            if item_id not in latest_prices or date > latest_prices[item_id].date:
                latest_prices[item_id] = price_obj

        # Sort by price descending
        top_expensive_items = sorted(latest_prices.values(), key=lambda item: item.price, reverse=True)[:5]
        market_trend_plots = []
        item_names_map = {p.item_id: p.item_name for (item_id, date), p in ops.market_prices.items()}
        unique_item_ids = sorted(list(item_names_map.keys()))
        print(f"DEBUG: analytics_page - IDs de ítems únicos para gráficos: {unique_item_ids}")  # <-- IMPORTANTE
        print(f"DEBUG: analytics_page - Número de ítems únicos: {len(unique_item_ids)}")  # <-- IMPORTANTE
        for item_id in unique_item_ids:
            trends = ops.get_market_trends(item_id)
            print(
                f"DEBUG: analytics_page - Procesando item_id: {item_id}, Trends obtenidos: {len(trends) if trends else 0}")  # <-- IMPORTANTE
            if trends:
                # Asegurarse de que los datos estén ordenados por fecha
                trends.sort(key=lambda p: datetime.strptime(p.date, "%Y-%m-%d"))

                dates = [datetime.strptime(p.date, "%Y-%m-%d") for p in trends]
                prices = [p.price for p in trends]
                item_name = trends[0].item_name if trends else "Unknown Item"  # Nombre del item

                # Crear el gráfico con Matplotlib
                fig, ax = plt.subplots(figsize=(8, 4))  # Tamaño del gráfico (ancho, alto)
                ax.plot(dates, prices, marker='o', linestyle='-')
                ax.set_title(f'Tendencia de Precios para "{item_name}" (ID: {item_id})')
                ax.set_xlabel('Fecha')
                ax.set_ylabel('Precio ($)')
                ax.grid(True)
                fig.autofmt_xdate()  # Rota las etiquetas de fecha para mejor legibilidad

                # Convertir el gráfico a una imagen PNG codificada en Base64
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight')
                plt.close(fig)  # Importante: cerrar la figura para liberar memoria
                buf.seek(0)
                image_base64 = base64.b64encode(buf.read()).decode('utf-8')

                market_trend_plots.append({
                    "item_id": item_id,
                    "item_name": item_name,
                    "plot_data": f"data:image/png;base64,{image_base64}"  # Formato para incrustar en HTML
                })
            else:
                print(f"DEBUG: analytics_page - No se encontraron tendencias para item_id: {item_id}")

            print(
                f"DEBUG: analytics_page - Gráficos de tendencia generados: {len(market_trend_plots)}")  # <-- IMPORTANTE

        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "ops": ops,
            "total_transactions": total_transactions,
            "total_players": total_players,
            "total_items": total_items,
            "total_spent_gta_dollars": total_spent_gta_dollars,
            "top_spenders": top_spenders,
            "top_expensive_items": top_expensive_items,
            "market_trend_plots": market_trend_plots,
        })
    except Exception as e:  # <--- Added try-except block
        print(f"Error in analytics_page: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {"request": request, "error_message": str(e)})


# --- Static Information Endpoints ---
@app.get("/developer", response_class=HTMLResponse)
async def developer_info_page(request: Request):
    """Renders the developer information page."""
    return templates.TemplateResponse("developer.html", {"request": request})


@app.get("/planning", response_class=HTMLResponse)
async def planning_page(request: Request):
    """Renders the project planning phase page."""
    return templates.TemplateResponse("planning.html", {"request": request})


@app.get("/design", response_class=HTMLResponse)
async def design_page(request: Request):
    """Renders the project design phase page."""
    return templates.TemplateResponse("design.html", {"request": request})


@app.get("/objective", response_class=HTMLResponse)
async def objective_page(request: Request):
    """Renders the project objective page."""
    return templates.TemplateResponse("objective.html", {"request": request})


# --- API Endpoints (as defined previously, keep if needed for external API access) ---

@app.post("/api/transactions/", response_model=TransactionResponse, status_code=201)
async def create_transaction_api(transaction: TransactionCreate):
    """Create a new transaction"""
    try:
        new_transaction = Transaction(
            transaction_id=transaction.transaction_id,
            player_id=transaction.player_id,
            item=transaction.item,
            amount=transaction.amount,
            date=transaction.date,
            transaction_type=transaction.transaction_type
        )
        ops.add_transaction(new_transaction)
        return new_transaction
    except (ValueError, TransactionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/transactions/", response_model=List[TransactionResponse])
async def get_all_transactions_api():
    """Get all transactions"""
    return list(ops.transactions.values())


@app.get("/api/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_single_transaction_api(transaction_id: int):
    """Get a single transaction by ID"""
    transaction = ops.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.put("/api/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_single_transaction_api(transaction_id: int, transaction: TransactionCreate):
    """Update a transaction (only amount for simplicity)"""
    try:
        ops.update_transaction(transaction_id, transaction.amount)
        updated_transaction = ops.get_transaction(transaction_id)
        return updated_transaction
    except TransactionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/transactions/{transaction_id}", status_code=204)
async def delete_single_transaction_api(transaction_id: int):
    """Delete a transaction"""
    try:
        ops.delete_transaction(transaction_id)
        return  # 204 No Content
    except TransactionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/market-prices/", response_model=MarketPriceResponse, status_code=201)
async def create_market_price_api(market_price: MarketPriceCreate):
    """Add a new market price entry"""
    try:
        new_market_price = MarketPrice(**market_price.model_dump())
        ops.add_market_price(new_market_price)
        return new_market_price
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/market-prices/", response_model=List[MarketPriceResponse])
async def get_all_market_prices_api():
    """Get all market price entries"""
    return ops.get_all_market_prices()


@app.get("/api/market-prices/{item_id}/latest", response_model=MarketPriceResponse)
async def get_latest_market_price_api(item_id: int):
    """Get the latest market price for a specific item"""
    price = ops.get_latest_market_price(item_id)
    if not price:
        raise HTTPException(status_code=404, detail=f"No market data found for item {item_id}")
    return price


@app.get("/api/market-prices/{item_id}/{date}", response_model=MarketPriceResponse)
async def get_market_price_by_date_api(item_id: int, date: str):
    """Get market price for a specific item on a specific date"""
    price = ops.get_market_price(item_id, date)
    if not price:
        raise HTTPException(status_code=404, detail=f"Market price for item {item_id} on {date} not found")
    return price


@app.delete("/api/market-prices/{item_id}/{date}", status_code=204)
async def delete_market_price_by_date_api(item_id: int, date: str):
    """Delete a specific market price entry"""
    try:
        ops.delete_market_price(item_id, date)
        return  # 204 No Content
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/market-prices/item/{item_id}", status_code=204)
async def delete_market_item_full_history_api(item_id: int):
    """Delete all market price entries for a specific item ID (full history)"""
    try:
        ops.delete_market_item_history(item_id)
        return  # 204 No Content
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/players/{player_id}", response_model=PlayerResponse)
async def get_player_info_api(player_id: str):
    """Get player information"""
    player = ops.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerResponse(**vars(player))  # Convert dataclass to Pydantic model


@app.put("/api/players/{player_id}/balance", response_model=PlayerResponse)
async def update_player_balance_api(player_id: str, new_balance: int = Query(..., gt=0)):
    """Update a player's balance"""
    try:
        ops.update_player_info(player_id, balance=new_balance)
        updated_player = ops.get_player(player_id)
        return PlayerResponse(**vars(updated_player))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/analytics/player-spending/{player_id}")
async def get_player_spending_analytics_api(player_id: str):
    """Get spending analytics for a specific player"""
    stats = ops.get_player_spending_stats(player_id)
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])
    return stats


@app.get("/api/analytics/top-spenders", response_model=List[PlayerResponse])
async def get_top_spenders_api(limit: int = Query(5, gt=0, le=100)):
    """Get top spending players"""
    top_players = ops.get_top_spenders(limit)
    return [PlayerResponse(**vars(p)) for p in top_players]


@app.get("/api/analytics/market-trends/{item_id}")
async def get_market_trends_api(item_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None):
    """Get market price trends for a specific item"""
    trends = ops.get_market_trends(item_id, from_date, to_date)
    if not trends:
        raise HTTPException(status_code=404, detail=f"No market data found for item {item_id}")

    return {
        "item_id": item_id,
        "item_name": trends[0].item_name if trends else "Unknown",
        "prices": [{"date": p.date, "price": p.price} for p in trends]
    }

if __name__ == "__main__":
    # Obtener el puerto del entorno (Render lo proporciona) o usar 8000 como predeterminado
    port = int(os.environ.get("PORT", 8000))
    # Iniciar el servidor uvicorn, vinculándolo a 0.0.0.0 para aceptar conexiones externasAdd commentMore actions
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
