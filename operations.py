from typing import Dict, List, Optional
from models import Transaction, MarketPrice, Player

class GTAOnlineOperations:
    def __init__(self):
        self.transactions: Dict[int, Transaction] = {}
        self.market_prices: Dict[tuple[int, str], MarketPrice] = {}  # Key: (item_id, date)
        self.players: Dict[str, Player] = {}

    # Transactions
    def add_transaction(self, transaction: Transaction) -> None:
        if transaction.transaction_id in self.transactions:
            raise ValueError(f"Transaction ID {transaction.transaction_id} already exists")
        self.transactions[transaction.transaction_id] = transaction
        # Update player's total_spent
        player = self.players.get(transaction.player_id)
        if player:
            player.total_spent += transaction.amount

    def get_all_transactions(self) -> List[Transaction]:
        return list(self.transactions.values())

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        return self.transactions.get(transaction_id)

    def update_transaction(self, transaction_id: int, new_transaction: Transaction) -> Transaction:
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction ID {transaction_id} not found")
        if new_transaction.transaction_id != transaction_id:
            raise ValueError("Transaction ID cannot be changed")
        # Adjust player's total_spent
        old_trans = self.transactions[transaction_id]
        player = self.players.get(old_trans.player_id)
        if player:
            player.total_spent -= old_trans.amount
            player.total_spent += new_transaction.amount
        self.transactions[transaction_id] = new_transaction
        return new_transaction

    def delete_transaction(self, transaction_id: int) -> None:
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction ID {transaction_id} not found")
        trans = self.transactions.pop(transaction_id)
        # Adjust player's total_spent
        player = self.players.get(trans.player_id)
        if player:
            player.total_spent -= trans.amount

    # Market Prices
    def add_market_price(self, market_price: MarketPrice) -> None:
        key = (market_price.item_id, market_price.date)
        if key in self.market_prices:
            raise ValueError(f"Market price for item {market_price.item_id} on {market_price.date} already exists")
        self.market_prices[key] = market_price

    def get_all_market_prices(self) -> List[MarketPrice]:
        return list(self.market_prices.values())

    def get_market_price_by_item_and_date(self, item_id: int, date: str) -> Optional[MarketPrice]:
        return self.market_prices.get((item_id, date))

    def update_market_price(self, item_id: int, date: str, new_price: MarketPrice) -> MarketPrice:
        key = (item_id, date)
        if key not in self.market_prices:
            raise ValueError(f"Market price for item {item_id} on {date} not found")
        self.market_prices[key] = new_price
        return new_price

    def delete_market_price(self, item_id: int, date: str) -> None:
        key = (item_id, date)
        if key not in self.market_prices:
            raise ValueError(f"Market price for item {item_id} on {date} not found")
        self.market_prices.pop(key)

    # Players
    def add_player(self, player: Player) -> None:
        if player.player_id in self.players:
            raise ValueError(f"Player ID {player.player_id} already exists")
        self.players[player.player_id] = player

    def get_all_players(self) -> List[Player]:
        return list(self.players.values())

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def update_player(self, player_id: str, new_player: Player) -> Player:
        if player_id not in self.players:
            raise ValueError(f"Player ID {player_id} not found")
        if new_player.player_id != player_id:
            raise ValueError("Player ID cannot be changed")
        self.players[player_id] = new_player
        return new_player

    def delete_player(self, player_id: str) -> None:
        if player_id not in self.players:
            raise ValueError(f"Player ID {player_id} not found")
        self.players.pop(player_id)

    # Analytical Methods
    def calculate_total_spending(self) -> int:
        return sum(trans.amount for trans in self.transactions.values())

    def calculate_average_transaction(self) -> float:
        transactions = self.transactions.values()
        return sum(trans.amount for trans in transactions) / len(transactions) if transactions else 0.0

    def calculate_inflation_rate(self, item_id: int, start_date: str, end_date: str) -> Optional[float]:
        prices = [price for (iid, date), price in self.market_prices.items() if iid == item_id]
        if not prices:
            return None
        prices.sort(key=lambda p: p.date)
        start_price = next((p.price for p in prices if p.date >= start_date), None)
        end_price = next((p.price for p in reversed(prices) if p.date <= end_date), None)
        if start_price is None or end_price is None:
            return None
        return ((end_price - start_price) / start_price) * 100 if start_price != 0 else None