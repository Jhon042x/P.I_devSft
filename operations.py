from models import Transaction, MarketPrice, Player

class GTAOnlineOperations:
    def __init__(self):
        self.transactions = []  # Lista para almacenar transacciones
        self.market_prices = []  # Lista para almacenar precios de ítems
        self.players = []  # Lista para almacenar jugadores

    def add_transaction(self, transaction):
        """Agrega una transacción a la lista y actualiza el gasto total del jugador."""
        if not isinstance(transaction, Transaction):
            raise ValueError("El objeto debe ser una instancia de Transaction")
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

    def get_transaction_by_id(self, transaction_id):
        """Busca una transacción por su ID."""
        for transaction in self.transactions:
            if transaction.transaction_id == transaction_id:
                return transaction
        return None

    def get_all_transactions(self):
        """Devuelve todas las transacciones."""
        return self.transactions

    def add_market_price(self, market_price):
        """Agrega un registro de precio de mercado."""
        if not isinstance(market_price, MarketPrice):
            raise ValueError("El objeto debe ser una instancia de MarketPrice")
        self.market_prices.append(market_price)
        return market_price

    def get_market_price_by_item_and_date(self, item_id, date):
        """Busca un precio de mercado por ID de ítem y fecha."""
        for price in self.market_prices:
            if price.item_id == item_id and price.date == date:
                return price
        return None

    def get_all_market_prices(self):
        """Devuelve todos los registros de precios de mercado."""
        return self.market_prices

    def add_player(self, player):
        """Agrega un jugador a la lista."""
        if not isinstance(player, Player):
            raise ValueError("El objeto debe ser una instancia de Player")
        if self.get_player_by_id(player.player_id) is None:
            self.players.append(player)
            return player
        raise ValueError(f"Jugador con ID {player.player_id} ya existe")

    def get_player_by_id(self, player_id):
        """Busca un jugador por su ID."""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def get_all_players(self):
        """Devuelve todos los jugadores."""
        return self.players

    def calculate_total_spending(self):
        """Calcula el total gastado en todas las transacciones."""
        return sum(transaction.amount for transaction in self.transactions)

    def calculate_average_transaction(self):
        """Calcula el monto promedio de las transacciones."""
        if not self.transactions:
            return 0
        return self.calculate_total_spending() / len(self.transactions)

    def calculate_inflation_rate(self, item_id, start_date, end_date):
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
            return None
        years = int(end_date[:4]) - int(start_date[:4])
        if years == 0:
            return 0
        return ((end_price / start_price) ** (1 / years) - 1) * 100  # Tasa de crecimiento anual compuesta (%)