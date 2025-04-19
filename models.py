from typing import Optional


class Transaction:
    """Modelo para representar una microtransacción en GTA Online."""
    def __init__(self, transaction_id: int, player_id: str, item: str, amount: int, date: str):
        """
        Inicializa una transacción.

        Args:
            transaction_id (int): ID único de la transacción.
            player_id (str): ID del jugador que realiza la compra.
            item (str): Ítem comprado (ej., 'Shark Card $500K').
            amount (int): Monto en GTA$ (dinero virtual).
            date (str): Fecha de la transacción (formato 'YYYY-MM-DD').
        """
        self.transaction_id: int = transaction_id
        self.player_id: str = player_id
        self.item: str = item
        self.amount: int = amount
        self.date: str = date

    def __str__(self) -> str:
        return f"Transacción {self.transaction_id}: {self.item} por ${self.amount:,} en {self.date} (Jugador: {self.player_id})"


class MarketPrice:
    """Modelo para representar el precio de un ítem en el mercado de GTA Online."""
    def __init__(self, item_id: int, item_name: str, price: int, date: str):
        """
        Inicializa un registro de precio de mercado.

        Args:
            item_id (int): ID único del ítem.
            item_name (str): Nombre del ítem (ej., 'Luxury Car').
            price (int): Precio en GTA$ en el mercado.
            date (str): Fecha del precio registrado (formato 'YYYY-MM-DD').
        """
        self.item_id: int = item_id
        self.item_name: str = item_name
        self.price: int = price
        self.date: str = date

    def __str__(self) -> str:
        return f"Precio de {self.item_name} (ID: {self.item_id}): ${self.price:,} en {self.date}"


class Player:
    """Modelo para representar un jugador en GTA Online."""
    def __init__(self, player_id: str, username: str, total_spent: int = 0):
        """
        Inicializa un jugador.

        Args:
            player_id (str): ID único del jugador.
            username (str): Nombre de usuario en GTA Online.
            total_spent (int, optional): Total gastado en microtransacciones (GTA$). Por defecto 0.
        """
        self.player_id: str = player_id
        self.username: str = username
        self.total_spent: int = total_spent

    def add_transaction(self, amount: int) -> None:
        """
        Actualiza el total gastado por el jugador.

        Args:
            amount (int): Monto de la transacción a agregar.

        Raises:
            ValueError: Si el monto es negativo.
        """
        if amount < 0:
            raise ValueError("El monto de la transacción no puede ser negativo")
        self.total_spent += amount

    def __str__(self) -> str:
        return f"Jugador {self.player_id} ({self.username}): Total gastado ${self.total_spent:,}"