from typing import Dict, List, Optional, Tuple
from models import Transaction, MarketPrice, Player
from datetime import datetime


class TransactionError(Exception):
    """Custom exception for transaction-related errors"""
    pass


class GTAOnlineOperations:
    def __init__(self):
        self.transactions: Dict[int, Transaction] = {}
        self.market_prices: Dict[Tuple[int, str], MarketPrice] = {}  # Key: (item_id, date)
        self.players: Dict[str, Player] = {}
        self._next_transaction_id = 1  # Auto-incrementing transaction ID

    # Transactions
    def add_transaction(self, transaction: Transaction, validate_balance: bool = True) -> None:
        """
        Add a new transaction. Can optionally validate if the player has sufficient balance.

        Args:
            transaction: The transaction to add
            validate_balance: If True, checks if the player has enough balance for the purchase

        Raises:
            ValueError: If transaction ID already exists
            TransactionError: If player doesn't exist or has insufficient balance
        """
        # Handle auto-incrementing transaction ID if not provided
        if transaction.transaction_id <= 0:
            transaction.transaction_id = self._get_next_transaction_id()
        elif transaction.transaction_id in self.transactions:
            raise ValueError(f"Transaction ID {transaction.transaction_id} already exists")

        # Auto-populate next ID for future transactions
        self._next_transaction_id = max(self._next_transaction_id, transaction.transaction_id + 1)

        # Check if player exists
        player = self.players.get(transaction.player_id)
        if not player:
            raise TransactionError(f"Player ID {transaction.player_id} not found")

        # For purchases, validate the player has enough balance
        if validate_balance and transaction.transaction_type == "purchase":
            if player.balance < transaction.amount:
                raise TransactionError(
                    f"Insufficient balance. Player {player.username} has {player.balance} but transaction requires {transaction.amount}"
                )
            # Deduct from player's balance
            player.balance -= transaction.amount
        elif transaction.transaction_type == "sale":
            # Add to player's balance for sales
            player.balance += transaction.amount

        # Add transaction and update player's total_spent for purchases
        self.transactions[transaction.transaction_id] = transaction
        if transaction.transaction_type == "purchase":
            player.total_spent += transaction.amount

    def _get_next_transaction_id(self) -> int:
        """Returns the next available transaction ID"""
        return self._next_transaction_id

    def get_all_transactions(self) -> List[Transaction]:
        """Returns all stored transactions"""
        return list(self.transactions.values())

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """Get a transaction by its ID"""
        return self.transactions.get(transaction_id)

    def get_player_transactions(self, player_id: str) -> List[Transaction]:
        """Get all transactions for a specific player"""
        return [t for t in self.transactions.values() if t.player_id == player_id]

    def update_transaction(self, transaction_id: int, new_transaction: Transaction) -> Transaction:
        """Update an existing transaction"""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction ID {transaction_id} not found")
        if new_transaction.transaction_id != transaction_id:
            raise ValueError("Transaction ID cannot be changed")

        # Adjust player's total_spent and balance
        old_trans = self.transactions[transaction_id]
        old_player = self.players.get(old_trans.player_id)
        new_player = self.players.get(new_transaction.player_id)

        if old_player and old_trans.transaction_type == "purchase":
            old_player.total_spent -= old_trans.amount
            old_player.balance += old_trans.amount  # Refund the old amount
        elif old_player and old_trans.transaction_type == "sale":
            old_player.balance -= old_trans.amount  # Remove the old sale amount

        if new_player and new_transaction.transaction_type == "purchase":
            if new_player.balance < new_transaction.amount:
                # Restore the old transaction and raise an error
                if old_player and old_trans.transaction_type == "purchase":
                    old_player.total_spent += old_trans.amount
                    old_player.balance -= old_trans.amount
                elif old_player and old_trans.transaction_type == "sale":
                    old_player.balance += old_trans.amount
                raise TransactionError(f"Insufficient balance for updated transaction")

            new_player.total_spent += new_transaction.amount
            new_player.balance -= new_transaction.amount
        elif new_player and new_transaction.transaction_type == "sale":
            new_player.balance += new_transaction.amount

        self.transactions[transaction_id] = new_transaction
        return new_transaction

    def delete_transaction(self, transaction_id: int) -> None:
        """Delete a transaction and adjust player's total_spent and balance"""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction ID {transaction_id} not found")

        trans = self.transactions.pop(transaction_id)
        player = self.players.get(trans.player_id)

        if player:
            if trans.transaction_type == "purchase":
                player.total_spent -= trans.amount
                player.balance += trans.amount  # Refund the amount
            elif trans.transaction_type == "sale":
                player.balance -= trans.amount  # Remove the sale amount

    # Market Prices
    def add_market_price(self, market_price: MarketPrice) -> None:
        """Add a new market price"""
        key = (market_price.item_id, market_price.date)
        if key in self.market_prices:
            raise ValueError(f"Market price for item {market_price.item_id} on {market_price.date} already exists")
        self.market_prices[key] = market_price

    def get_all_market_prices(self) -> List[MarketPrice]:
        """Get all market prices"""
        return list(self.market_prices.values())

    def get_market_price_by_item_and_date(self, item_id: int, date: str) -> Optional[MarketPrice]:
        """Get market price for a specific item on a specific date"""
        return self.market_prices.get((item_id, date))

    def get_latest_market_price(self, item_id: int) -> Optional[MarketPrice]:
        """Get the most recent market price for a specific item"""
        prices = [p for (iid, _), p in self.market_prices.items() if iid == item_id]
        if not prices:
            return None
        return max(prices, key=lambda p: p.date)

    def update_market_price(self, item_id: int, date: str, new_price: MarketPrice) -> MarketPrice:
        """Update an existing market price"""
        key = (item_id, date)
        if key not in self.market_prices:
            raise ValueError(f"Market price for item {item_id} on {date} not found")
        self.market_prices[key] = new_price
        return new_price

    def delete_market_price(self, item_id: int, date: str) -> None:
        """Delete a market price"""
        key = (item_id, date)
        if key not in self.market_prices:
            raise ValueError(f"Market price for item {item_id} on {date} not found")
        self.market_prices.pop(key)

    # Players
    def add_player(self, player: Player, with_random_balance: bool = True) -> Player:
        """
        Add a new player

        Args:
            player: The player to add
            with_random_balance: If True and player.balance is 0, generate a random balance

        Returns:
            The added player

        Raises:
            ValueError: If player ID already exists
        """
        if player.player_id in self.players:
            raise ValueError(f"Player ID {player.player_id} already exists")

        # Generate random balance if requested and no balance is set
        if with_random_balance and player.balance == 0:
            from models import Player as PlayerModel
            player = PlayerModel.create_with_random_balance(
                player_id=player.player_id,
                username=player.username,
                total_spent=player.total_spent
            )

        self.players[player.player_id] = player
        return player

    def get_all_players(self) -> List[Player]:
        """Get all players"""
        return list(self.players.values())

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """Get a player by ID"""
        return self.players.get(player_id)

    def get_player_by_username(self, username: str) -> Optional[Player]:
        """Get a player by username"""
        for player in self.players.values():
            if player.username.lower() == username.lower():
                return player
        return None

    def update_player(self, player_id: str, new_player: Player) -> Player:
        """Update an existing player"""
        if player_id not in self.players:
            raise ValueError(f"Player ID {player_id} not found")
        if new_player.player_id != player_id:
            raise ValueError("Player ID cannot be changed")
        self.players[player_id] = new_player
        return new_player

    def delete_player(self, player_id: str) -> None:
        """Delete a player"""
        if player_id not in self.players:
            raise ValueError(f"Player ID {player_id} not found")
        self.players.pop(player_id)

    # Analytical Methods
    def calculate_total_spending(self) -> int:
        """Calculate total spending across all transactions"""
        return sum(trans.amount for trans in self.transactions.values()
                   if trans.transaction_type == "purchase")

    def calculate_average_transaction(self, transaction_type: Optional[str] = None) -> float:
        """
        Calculate average transaction amount

        Args:
            transaction_type: Optional filter by transaction type ("purchase" or "sale")

        Returns:
            The average transaction amount
        """
        if transaction_type:
            transactions = [t for t in self.transactions.values() if t.transaction_type == transaction_type]
        else:
            transactions = self.transactions.values()

        return sum(trans.amount for trans in transactions) / len(transactions) if transactions else 0.0

    def calculate_inflation_rate(self, item_id: int, start_date: str, end_date: str) -> Optional[float]:
        """Calculate inflation rate for a specific item between two dates"""
        prices = [price for (iid, date), price in self.market_prices.items() if iid == item_id]
        if not prices:
            return None

        prices.sort(key=lambda p: p.date)
        start_price = next((p.price for p in prices if p.date >= start_date), None)
        end_price = next((p.price for p in reversed(prices) if p.date <= end_date), None)

        if start_price is None or end_price is None:
            return None

        if start_price == 0:
            return None  # Avoid division by zero

        return ((end_price - start_price) / start_price) * 100

    def get_player_spending_stats(self, player_id: str) -> dict:
        """
        Get spending statistics for a specific player

        Returns:
            Dictionary with spending statistics
        """
        player = self.get_player_by_id(player_id)
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
        """Get top spending players"""
        return sorted(self.players.values(), key=lambda p: p.total_spent, reverse=True)[:limit]

    def get_market_trends(self, item_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[
        MarketPrice]:
        """Get market price trends for a specific item"""
        prices = [p for (iid, _), p in self.market_prices.items() if iid == item_id]

        if from_date:
            prices = [p for p in prices if p.date >= from_date]
        if to_date:
            prices = [p for p in prices if p.date <= to_date]

        return sorted(prices, key=lambda p: p.date)