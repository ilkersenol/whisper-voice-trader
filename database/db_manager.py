"""
Database Manager - SQLite connection and initialization
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path(__file__).parent.parent / "data" / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "trading.db")
        
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        logger.info(f"DatabaseManager initialized with path: {db_path}")
    
    def connect(self) -> sqlite3.Connection:
        """Create database connection"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.debug("Database connection established")
        return self.connection
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Database connection closed")
    
    def initialize(self):
        """Initialize database with schema"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        conn = self.connect()
        try:
            conn.executescript(schema_sql)
            conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
            raise
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_setting(self, key: str) -> Optional[str]:
        """Get setting value by key"""
        result = self.fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
        return result['value'] if result else None
    
    def set_setting(self, key: str, value: str):
        """Set setting value"""
        self.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        logger.debug(f"Setting updated: {key} = {value}")


        # --- Trade History Helpers (trade_history tablosu) ---

    def insert_trade_history(self, trade_data: dict) -> int:
        """
        trade_history tablosuna yeni trade kaydı ekler.
        trade_data: database/schema.sql içindeki trade_history kolonlarıyla uyumlu olmalı.
        """
        fields = [
            "exchange",
            "order_id",
            "symbol",
            "side",
            "quantity",
            "price",
            "pnl",
            "commission",
            "commission_asset",
            "is_paper_trade",
        ]
        placeholders = ", ".join(["?"] * len(fields))
        values = [trade_data.get(f) for f in fields]

        query = f"""
            INSERT INTO trade_history ({", ".join(fields)})
            VALUES ({placeholders})
        """

        cursor = self.execute(query, tuple(values))
        return cursor.lastrowid

    def get_trades_by_order_id(self, order_id: int) -> list[dict]:
        """
        Belirli bir order_id'ye ait tüm trade kayıtlarını döndürür.
        """
        query = """
            SELECT *
            FROM trade_history
            WHERE order_id = ?
            ORDER BY created_at ASC
        """
        return self.fetch_all(query, (order_id,))

    def get_recent_trades(self, limit: int = 50) -> list[dict]:
        """
        En son N trade kaydını döndürür.
        """
        query = """
            SELECT *
            FROM trade_history
            ORDER BY created_at DESC
            LIMIT ?
        """
        return self.fetch_all(query, (limit,))
    
        # --- System Logs Helpers (system_logs tablosu) ---

    def insert_system_log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Sistem log kaydı.
        - system_logs tablosu yoksa sessizce geçer.
        - Başka bir hata olursa da uygulamayı BOZMAZ, sessiz geçer.
        """
        import json
        import sqlite3

        context_json = json.dumps(context or {})

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO system_logs (level, message, context, created_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (level, message, context_json),
                )
        except sqlite3.OperationalError as e:
            # Tablo yoksa, log yazmayalım ama uygulamayı da bozmayalım
            if "no such table: system_logs" in str(e):
                return
            # başka bir SQLite hatasıysa, yukarı fırlat
            raise
        except Exception:
            # Her türlü başka hatada da sessizce geç
            return




    
    def save_api_keys(self, exchange: str, api_key: str, secret_key: str, 
                      passphrase: Optional[str] = None, encrypted: bool = True) -> bool:
        """
        Save API keys for an exchange
        
        Args:
            exchange: Exchange name (binance, bybit, etc.)
            api_key: API key (encrypted or plain)
            secret_key: Secret key (encrypted or plain)
            passphrase: Optional passphrase (for some exchanges)
            encrypted: Whether keys are already encrypted
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # If not encrypted, encrypt them
            if not encrypted:
                from utils.encryption import get_encryption_manager
                em = get_encryption_manager()
                api_key = em.encrypt_to_base64(api_key)
                secret_key = em.encrypt_to_base64(secret_key)
                if passphrase:
                    passphrase = em.encrypt_to_base64(passphrase)
            
            # Update exchange record
            self.execute(
                """UPDATE exchanges 
                   SET api_key = ?, secret_key = ?, passphrase = ?, is_configured = 1, updated_at = CURRENT_TIMESTAMP
                   WHERE name = ?""",
                (api_key, secret_key, passphrase, exchange)
            )
            logger.info(f"API keys saved for {exchange}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save API keys for {exchange}: {e}")
            return False
    
    def load_api_keys(self, exchange: str, decrypt: bool = True) -> Optional[Dict[str, str]]:
        """
        Load API keys for an exchange
        
        Args:
            exchange: Exchange name
            decrypt: Whether to decrypt keys
            
        Returns:
            Dictionary with api_key, secret_key, passphrase or None
        """
        try:
            result = self.fetch_one(
                "SELECT api_key, secret_key, passphrase FROM exchanges WHERE name = ?",
                (exchange,)
            )
            
            if not result or not result.get('api_key'):
                logger.warning(f"No API keys found for {exchange}")
                return None
            
            keys = {
                'api_key': result['api_key'],
                'secret_key': result['secret_key'],
                'passphrase': result.get('passphrase')
            }
            
            # Decrypt if requested
            if decrypt and keys['api_key']:
                from utils.encryption import get_encryption_manager
                em = get_encryption_manager()
                try:
                    keys['api_key'] = em.decrypt_from_base64(keys['api_key'])
                    keys['secret_key'] = em.decrypt_from_base64(keys['secret_key'])
                    if keys['passphrase']:
                        keys['passphrase'] = em.decrypt_from_base64(keys['passphrase'])
                except Exception as e:
                    logger.error(f"Failed to decrypt keys for {exchange}: {e}")
                    return None
            
            logger.debug(f"API keys loaded for {exchange}")
            return keys
            
        except Exception as e:
            logger.error(f"Failed to load API keys for {exchange}: {e}")
            return None
    
    def delete_api_keys(self, exchange: str) -> bool:
        """
        Delete API keys for an exchange
        
        Args:
            exchange: Exchange name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                """UPDATE exchanges 
                   SET api_key = NULL, secret_key = NULL, passphrase = NULL, 
                       is_configured = 0, is_connected = 0, updated_at = CURRENT_TIMESTAMP
                   WHERE name = ?""",
                (exchange,)
            )
            logger.info(f"API keys deleted for {exchange}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete API keys for {exchange}: {e}")
            return False
    
    def update_exchange_status(self, exchange: str, is_connected: bool) -> bool:
        """
        Update exchange connection status
        
        Args:
            exchange: Exchange name
            is_connected: Connection status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                "UPDATE exchanges SET is_connected = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (1 if is_connected else 0, exchange)
            )
            logger.debug(f"Exchange status updated: {exchange} -> {is_connected}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update exchange status for {exchange}: {e}")
            return False
    
    def get_configured_exchanges(self) -> List[str]:
        """
        Get list of configured exchanges
        
        Returns:
            List of exchange names that have API keys configured
        """
        try:
            results = self.fetch_all(
                "SELECT name FROM exchanges WHERE is_configured = 1"
            )
            return [r['name'] for r in results]
            
        except Exception as e:
            logger.error(f"Failed to get configured exchanges: {e}")
            return []
    
    def get_connected_exchanges(self) -> List[str]:
        """
        Get list of connected exchanges
        
        Returns:
            List of exchange names that are currently connected
        """
        try:
            results = self.fetch_all(
                "SELECT name FROM exchanges WHERE is_connected = 1"
            )
            return [r['name'] for r in results]
            
        except Exception as e:
            logger.error(f"Failed to get connected exchanges: {e}")
            return []
    # db_manager.py içinde DatabaseManager class'ına ekleyin:

        # ------------------------------------------------------------------
    # ORDERS TABLE HELPERS
    # ------------------------------------------------------------------
    def insert_order(self, order_data: Dict[str, Any]) -> int:
        """
        Insert new order into 'orders' table.

        Beklenen alanlar:
        - exchange, symbol, side, type, quantity (zorunlu)
        - exchange_order_id, price, stop_price, leverage, status,
          filled_quantity, average_fill_price, commission,
          commission_asset, position_id, is_paper_trade, voice_command (opsiyonel)
        """
        fields = [
            "exchange",
            "exchange_order_id",
            "symbol",
            "side",
            "type",
            "quantity",
            "price",
            "stop_price",
            "leverage",
            "status",
            "filled_quantity",
            "average_fill_price",
            "commission",
            "commission_asset",
            "position_id",
            "is_paper_trade",
            "voice_command",
        ]

        values = [order_data.get(f) for f in fields]
        placeholders = ", ".join(["?"] * len(fields))

        query = f"""
            INSERT INTO orders ({", ".join(fields)})
            VALUES ({placeholders})
        """

        cursor = self.execute(query, tuple(values))
        return cursor.lastrowid

    def update_order_status(
        self,
        order_id: int,
        status: str,
        filled_quantity: Optional[float] = None,
        average_fill_price: Optional[float] = None,
        commission: Optional[float] = None,
        commission_asset: Optional[str] = None,
    ) -> bool:
        """
        Update order status and optional execution fields.
        """
        fields = ["status"]
        params: List[Any] = [status]

        if filled_quantity is not None:
            fields.append("filled_quantity")
            params.append(filled_quantity)

        if average_fill_price is not None:
            fields.append("average_fill_price")
            params.append(average_fill_price)

        if commission is not None:
            fields.append("commission")
            params.append(commission)

        if commission_asset is not None:
            fields.append("commission_asset")
            params.append(commission_asset)

        set_clause = ", ".join(f"{f} = ?" for f in fields)
        query = f"UPDATE orders SET {set_clause} WHERE id = ?"
        params.append(order_id)

        self.execute(query, tuple(params))
        return True

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get single order by id."""
        return self.fetch_one("SELECT * FROM orders WHERE id = ?", (order_id,))

    def get_recent_orders(
        self,
        limit: int = 50,
        is_paper_trade: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent orders, optionally filtered by paper/real flag.
        """
        base_query = "SELECT * FROM orders"
        params: List[Any] = []

        if is_paper_trade is not None:
            base_query += " WHERE is_paper_trade = ?"
            params.append(1 if is_paper_trade else 0)

        base_query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        return self.fetch_all(base_query, tuple(params))


    def __del__(self):
            """Destructor - ensure connection is closed"""
            self.disconnect()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
        return False

# Global instance
_db_instance: Optional[DatabaseManager] = None

def get_db() -> DatabaseManager:
    """Get global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
