from dataclasses import dataclass

@dataclass
class Transaction:
    transaction_id: int
    player_id: str
    item: str
    amount: int
    date: str

@dataclass
class MarketPrice:
    item_id: int
    item_name: str
    price: int
    date: str

@dataclass
class Player:
    player_id: str
    username: str
    total_spent: int = 0