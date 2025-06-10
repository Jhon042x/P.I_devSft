from typing import Dict, List, Optional, Tuple, Any
from models import Transaction, MarketPrice, Player
from datetime import datetime
import json
import os


class TransactionError(Exception):
    """Custom exception for transaction-related errors"""
    pass


class GTAOnlineOperations:
    def __init__(self):
        self.transactions: Dict[int, Transaction] = {}
        self.market_prices: Dict[Tuple[int, str], MarketPrice] = {}  # Key: (item_id, date)
        self.players: Dict[str, Player] = {}
        self.item_images: Dict[str, str] = {}  # Key: item_id (str), Value: image_filename (str)

        # Auto-incrementing IDs
        self._next_transaction_id = 1
        # _next_market_item_id será inicializado en startup_event basado en datos existentes
        # _next_player_id_counter es para un posible auto-generador de IDs de jugador (no usado actualmente en forms)
        self._next_player_id_counter = 1

        # --- Helper for ID generation ---

    def _get_next_transaction_id(self) -> int:
        """Generates the next available transaction ID."""
        current_id = self._next_transaction_id
        self._next_transaction_id += 1
        return current_id

    def _get_next_market_item_id(self) -> int:
        """Generates the next available market item ID based on existing items."""
        if not self.market_prices:
            return 1
        # Extraer todos los item_id de las claves (item_id, date)
        max_id = max(item_id for item_id, _ in self.market_prices.keys())
        return max_id + 1

    def _get_next_player_id_counter(self) -> int:
        """
        Initializes the player ID counter based on existing players if they use 'player_XXXX' format.
        (Currently, player IDs are user-provided in the forms, so this is mainly for future auto-generation).
        """
        if not self.players:
            return 1
        max_suffix = 0
        for player_id in self.players.keys():
            if player_id.startswith("player_") and player_id[7:].isdigit():
                try:
                    suffix = int(player_id[7:])
                    if suffix > max_suffix:
                        max_suffix = suffix
                except ValueError:
                    pass  # Ignore if not in expected format
        return max_suffix + 1

    # --- Transactions ---
    def add_transaction(self, transaction: Transaction, validate_balance: bool = True) -> None:
        """
        Add a new transaction. Can optionally validate if the player has sufficient balance.
        Args:
            transaction: The transaction to add
            validate_balance: If True, checks if the player has enough balance for the purchase
        Raises:
            ValueError: If transaction ID already exists
            TransactionError: If player doesn't exist, item doesn't exist, or has insufficient balance
        """
        if transaction.transaction_id <= 0:
            transaction.transaction_id = self._get_next_transaction_id()
        elif transaction.transaction_id in self.transactions:
            raise ValueError(f"Transaction ID {transaction.transaction_id} already exists")

        player = self.players.get(transaction.player_id)
        if not player:
            raise TransactionError(f"Player {transaction.player_id} not found")

        # Basic item existence check (by name, assumes item name is unique enough for transactions)
        item_exists = False
        for (mp_item_id, mp_date), mp_price_obj in self.market_prices.items():
            if mp_price_obj.item_name == transaction.item:
                item_exists = True
                break

        if not item_exists:
            raise TransactionError(
                f"Item '{transaction.item}' not found in market prices. Cannot complete transaction.")

        if validate_balance:
            if transaction.transaction_type == "purchase":
                if player.balance < transaction.amount:
                    raise TransactionError(
                        f"Player {player.username} has insufficient balance for transaction (needs ${transaction.amount}). Current balance: ${player.balance}.")
                player.balance -= transaction.amount
                player.total_spent += transaction.amount
            elif transaction.transaction_type == "sale":
                player.balance += transaction.amount  # Add amount back to balance on sale

        self.transactions[transaction.transaction_id] = transaction

    def get_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """Get a transaction by its ID."""
        return self.transactions.get(transaction_id)

    def get_player_transactions(self, player_id: str) -> List[Transaction]:
        """Get all transactions for a specific player."""
        return [t for t in self.transactions.values() if t.player_id == player_id]

    def update_transaction(self, transaction_id: int, new_amount: int) -> None:
        """Update an existing transaction's amount."""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            raise TransactionError(f"Transaction {transaction_id} not found")
        # Note: A real system would need more complex logic for balance adjustments on update
        transaction.amount = new_amount

    def delete_transaction(self, transaction_id: int) -> None:
        """Delete a transaction and revert player balance/total_spent."""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            raise TransactionError(f"Transaction {transaction_id} not found")

        player = self.players.get(transaction.player_id)
        if player:
            if transaction.transaction_type == "purchase":
                player.balance += transaction.amount  # Revert balance
                player.total_spent -= transaction.amount  # Revert spent
            elif transaction.transaction_type == "sale":
                player.balance -= transaction.amount  # Revert balance

        del self.transactions[transaction_id]

    # --- Market Prices (Items) ---
    def add_market_price(self, market_price: MarketPrice) -> None:
        """Add a new market price entry for an item."""
        key = (market_price.item_id, market_price.date)
        if key in self.market_prices:
            # You might want to update instead of raising an error here, depending on desired behavior
            raise ValueError(f"Market price for item {market_price.item_id} on {market_price.date} already exists.")
        self.market_prices[key] = market_price

    def get_market_price(self, item_id: int, date: str) -> Optional[MarketPrice]:
        """Get a market price for a specific item on a specific date."""
        return self.market_prices.get((item_id, date))

    def get_latest_market_price(self, item_id: int) -> Optional[MarketPrice]:
        """Get the latest recorded market price for a specific item."""
        latest_price = None
        for (mp_item_id, mp_date), price_obj in self.market_prices.items():
            if mp_item_id == item_id:
                if latest_price is None or price_obj.date > latest_price.date:
                    latest_price = price_obj
        return latest_price

    def get_all_market_prices(self) -> List[MarketPrice]:
        """Get all recorded market prices."""
        return list(self.market_prices.values())

    def update_market_price(self, item_id: int, date: str, new_price: Optional[int] = None,
                            new_item_name: Optional[str] = None) -> None:
        """Update an existing market price entry."""
        key = (item_id, date)
        market_price = self.market_prices.get(key)
        if not market_price:
            raise ValueError(f"Market price for item {item_id} on {date} not found.")
        if new_price is not None:
            market_price.price = new_price
        if new_item_name is not None:
            market_price.item_name = new_item_name
        # Note: If item_id or date needs to change, it's effectively a delete + add.

    def delete_market_price(self, item_id: int, date: str) -> None:
        """Delete a specific market price entry."""
        key = (item_id, date)
        if key not in self.market_prices:
            raise ValueError(f"Market price for item {item_id} on {date} not found.")
        del self.market_prices[key]

    def delete_market_item_history(self, item_id: int) -> None:
        """Deletes all historical price entries for a given item ID."""
        keys_to_delete = [(iid, date) for iid, date in self.market_prices.keys() if iid == item_id]
        if not keys_to_delete:
            raise ValueError(f"No market data found for item {item_id}")
        for key in keys_to_delete:
            del self.market_prices[key]

        # Also remove associated image
        if str(item_id) in self.item_images:
            image_filename = self.item_images[str(item_id)]
            image_path = os.path.join("static/images", image_filename)
            if os.path.exists(image_path) and image_filename != 'default.png':
                os.remove(image_path)
            del self.item_images[str(item_id)]

    # --- Players ---
    def add_player(self, player: Player) -> None:
        """Add a new player."""
        if player.player_id in self.players:
            raise ValueError(f"Player ID {player.player_id} already exists.")
        self.players[player.player_id] = player

    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by their ID."""
        return self.players.get(player_id)

    def update_player_info(self, player_id: str, username: Optional[str] = None, balance: Optional[int] = None) -> None:
        """Update a player's username and/or balance."""
        player = self.players.get(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")
        if username is not None:
            player.username = username
        if balance is not None:
            player.balance = balance

    def delete_player(self, player_id: str) -> None:
        """Delete a player and all their associated transactions."""
        if player_id not in self.players:
            raise ValueError(f"Player {player_id} not found")

        # Eliminar transacciones asociadas a este jugador
        transactions_to_delete = [
            trans_id for trans_id, trans_obj in self.transactions.items()
            if trans_obj.player_id == player_id
        ]
        for trans_id in transactions_to_delete:
            del self.transactions[trans_id]

        del self.players[player_id]

    # --- Analytics & Reporting ---
    def get_player_spending_stats(self, player_id: str) -> Dict[str, Any]:
        """Get spending statistics for a specific player."""
        player = self.players.get(player_id)
        if not player:
            return {"error": f"Player {player_id} not found"}

        transactions = self.get_player_transactions(player_id)
        purchases = [t for t in transactions if t.transaction_type == "purchase"]
        sales = [t for t in transactions if t.transaction_type == "sale"]

        return {
            "player_id": player_id,
            "username": player.username,
            "current_balance": player.balance,
            "total_spent": player.total_spent,
            "purchase_count": len(purchases),
            "sale_count": len(sales),
            "avg_purchase": sum(t.amount for t in purchases) / len(purchases) if purchases else 0,
            "avg_sale": sum(t.amount for t in sales) / len(sales) if sales else 0,
        }

    def get_top_spenders(self, limit: int = 5) -> List[Player]:
        """Get top spending players."""
        return sorted(self.players.values(), key=lambda p: p.total_spent, reverse=True)[:limit]

    def get_market_trends(self, item_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[
        MarketPrice]:
        """Get market price trends for a specific item within a date range."""
        prices = [p for (iid, _), p in self.market_prices.items() if iid == item_id]
        if from_date:
            prices = [p for p in prices if p.date >= from_date]
        if to_date:
            prices = [p for p in prices if p.date <= to_date]
        return sorted(prices, key=lambda p: p.date)