from dataclasses import dataclass
from typing import Optional
import random


@dataclass
class Transaction:
    transaction_id: int
    player_id: str
    item: str
    amount: int
    date: str
    # Adding transaction type (purchase/sale)
    transaction_type: str = "purchase"


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
    balance: int  # Player's current balance
    total_spent: int = 0

    @classmethod
    def create_with_random_balance(cls, player_id: str, username: str, total_spent: int = 0) -> 'Player':
        """Create a new player with a random balance between 100,000 and 10,000,000"""
        random_balance = random.randint(100000, 10000000)
        return cls(player_id=player_id, username=username, balance=random_balance, total_spent=total_spent)