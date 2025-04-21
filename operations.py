from typing import Any

from models import Transaction, MarketPrice, Player


class GTAOnlineOperations:
    def __init__(self):
        self.transactions = []  # Lista para almacenar transacciones
        self.market_prices = []  # Lista para almacenar precios de ítems
        self.players = []  # Lista para almacenar jugadores

    def add_transaction(self, transaction: Transaction) -> Transaction:
        """Agrega una transacción a la lista y actualiza el gasto total del jugador."""
        if not isinstance(transaction, Transaction):
            raise ValueError("El objeto debe ser una instancia de Transaction")
        # Verificar si el ID de la transacción ya existe
        if self.get_transaction_by_id(transaction.transaction_id):
            raise ValueError(f"Transacción con ID {transaction.transaction_id} ya existe")
        self.transactions.append(transaction)
        # Actualizar el total gastado del jugador
        player = self.get_player_by_id(transaction.player_id)
        if player:
            player.add_transaction(transaction.amount)
        else:
            # Si el jugador no existe, crear uno nuevo con nombre genérico
            new_player = Player(transaction.player_id, f"User_{transaction.player_id}")
            new_player.add_transaction(transaction.amount)
            self.players.append(new_player)
        return transaction

    def update_transaction(self, transaction_id: int, updated_transaction: Transaction) -> Transaction:
        """Actualiza una transacción existente."""
        if not isinstance(updated_transaction, Transaction):
            raise ValueError("El objeto debe ser una instancia de Transaction")
        if updated_transaction.transaction_id != transaction_id:
            raise ValueError("El ID de la transacción no coincide con el proporcionado")

        # Buscar la transacción existente
        for i, trans in enumerate(self.transactions):
            if trans.transaction_id == transaction_id:
                # Revertir el monto anterior en el jugador
                old_player = self.get_player_by_id(trans.player_id)
                if old_player:
                    old_player.add_transaction(-trans.amount)  # Restar el monto antiguo
                # Actualizar la transacción
                self.transactions[i] = updated_transaction
                # Actualizar el monto nuevo en el jugador
                new_player = self.get_player_by_id(updated_transaction.player_id)
                if new_player:
                    new_player.add_transaction(updated_transaction.amount)
                else:
                    new_player = Player(updated_transaction.player_id, f"User_{updated_transaction.player_id}")
                    new_player.add_transaction(updated_transaction.amount)
                    self.players.append(new_player)
                return updated_transaction
        raise ValueError(f"Transacción con ID {transaction_id} no encontrada")

    def delete_transaction(self, transaction_id: int) -> None:
        """Elimina una transacción por su ID."""
        for i, trans in enumerate(self.transactions):
            if trans.transaction_id == transaction_id:
                # Revertir el monto en el jugador
                player = self.get_player_by_id(trans.player_id)
                if player:
                    player.add_transaction(-trans.amount)  # Restar el monto
                self.transactions.pop(i)
                return
        raise ValueError(f"Transacción con ID {transaction_id} no encontrada")

    def get_transaction_by_id(self, transaction_id: int) -> Any | None:
        """Busca una transacción por su ID."""
        for transaction in self.transactions:
            if transaction.transaction_id == transaction_id:
                return transaction
        return Any

    def get_all_transactions(self) -> list:
        """Devuelve todas las transacciones."""
        return self.transactions

    def add_market_price(self, market_price: MarketPrice) -> MarketPrice:
        """Agrega un registro de precio de mercado."""
        if not isinstance(market_price, MarketPrice):
            raise ValueError("El objeto debe ser una instancia de MarketPrice")
        # Verificar si ya existe un precio para el mismo ítem y fecha
        if self.get_market_price_by_item_and_date(market_price.item_id, market_price.date):
            raise ValueError(f"Precio para ítem {market_price.item_id} en {market_price.date} ya existe")
        self.market_prices.append(market_price)
        return market_price

    def update_market_price(self, item_id: int, date: str, updated_market_price: MarketPrice) -> MarketPrice:
        """Actualiza un precio de mercado existente."""
        if not isinstance(updated_market_price, MarketPrice):
            raise ValueError("El objeto debe ser una instancia de MarketPrice")
        if updated_market_price.item_id != item_id or updated_market_price.date != date:
            raise ValueError("El ID del ítem o la fecha no coinciden con los proporcionados")

        for i, price in enumerate(self.market_prices):
            if price.item_id == item_id and price.date == date:
                self.market_prices[i] = updated_market_price
                return updated_market_price
        raise ValueError(f"Precio para ítem {item_id} en {date} no encontrado")

    def delete_market_price(self, item_id: int, date: str) -> None:
        """Elimina un precio de mercado por ID de ítem y fecha."""
        for i, price in enumerate(self.market_prices):
            if price.item_id == item_id and price.date == date:
                self.market_prices.pop(i)
                return
        raise ValueError(f"Precio para ítem {item_id} en {date} no encontrado")

    def get_market_price_by_item_and_date(self, item_id: int, date: str) -> MarketPrice:
        """Busca un precio de mercado por ID de ítem y fecha."""
        for price in self.market_prices:
            if price.item_id == item_id and price.date == date:
                return price
        return Any

    def get_all_market_prices(self) -> list:
        """Devuelve todos los registros de precios de mercado."""
        return self.market_prices

    def add_player(self, player: Player) -> Player:
        """Agrega un jugador a la lista."""
        if not isinstance(player, Player):
            raise ValueError("El objeto debe ser una instancia de Player")
        if self.get_player_by_id(player.player_id) is not None:
            raise ValueError(f"Jugador con ID {player.player_id} ya existe")
        self.players.append(player)
        return player

    def update_player(self, player_id: str, updated_player: Player) -> Player:
        """Actualiza un jugador existente."""
        if not isinstance(updated_player, Player):
            raise ValueError("El objeto debe ser una instancia de Player")
        if updated_player.player_id != player_id:
            raise ValueError("El ID del jugador no coincide con el proporcionado")

        for i, player in enumerate(self.players):
            if player.player_id == player_id:
                # Verificar que el total_spent sea consistente con las transacciones
                if updated_player.total_spent < 0:
                    raise ValueError("El total gastado no puede ser negativo")
                self.players[i] = updated_player
                return updated_player
        raise ValueError(f"Jugador con ID {player_id} no encontrado")

    def delete_player(self, player_id: str) -> None:
        """Elimina un jugador por su ID."""
        # Verificar si el jugador tiene transacciones asociadas
        for trans in self.transactions:
            if trans.player_id == player_id:
                raise ValueError(f"No se puede eliminar el jugador {player_id} porque tiene transacciones asociadas")
        for i, player in enumerate(self.players):
            if player.player_id == player_id:
                self.players.pop(i)
                return
        raise ValueError(f"Jugador con ID {player_id} no encontrado")

    def get_player_by_id(self, player_id: str) -> Player:
        """Busca un jugador por su ID."""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return Any

    def get_all_players(self) -> list:
        """Devuelve todos los jugadores."""
        return self.players

    def calculate_total_spending(self) -> int:
        """Calcula el total gastado en todas las transacciones."""
        return sum(transaction.amount for transaction in self.transactions)

    def calculate_average_transaction(self) -> float:
        """Calcula el monto promedio de las transacciones."""
        if not self.transactions:
            return 0
        return self.calculate_total_spending() / len(self.transactions)

    def calculate_inflation_rate(self, item_id: int, start_date: str, end_date: str) -> float:
        """Calcula la tasa de inflación para un ítem entre dos fechas."""
        start_price = None
        end_price = None
        for price in self.market_prices:
            if price.item_id == item_id:
                if price.date == start_date:
                    start_price = price.price
                if price.date == end_date:
                    end_price = price.price
        if start_price is None or end_price is None:
            return Any
        years = int(end_date[:4]) - int(start_date[:4])
        if years == 0:
            return 0
        return ((end_price / start_price) ** (1 / years) - 1) * 100  # Tasa de crecimiento anual compuesta (%)