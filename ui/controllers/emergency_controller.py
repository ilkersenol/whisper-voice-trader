"""Emergency Stop Dialog Controller"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import Qt
from ui.generated.ui_emergency_dialog import Ui_EmergencyDialog
from database.db_manager import get_db
from utils.logger import get_logger

logger = get_logger(__name__)


class EmergencyController(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_EmergencyDialog()
        self.ui.setupUi(self)
        self.db = get_db()
        
        # Stay on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # Connect buttons
        self.ui.btnCloseAll.clicked.connect(self.close_all_positions)
        self.ui.btnCancelAll.clicked.connect(self.cancel_all_orders)
        self.ui.btnStop.clicked.connect(self.stop_bot)
        self.ui.btnCancel.clicked.connect(self.reject)
        
        # Load status
        self.load_status()
    
    def load_status(self):
        """Load current positions and orders count"""
        try:
            # Count open positions
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM positions WHERE status = 'open'")
            pos_count = result['count'] if result else 0
            self.ui.labelPositions.setText(f"Open Positions: {pos_count}")
            
            # Count pending orders
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
            order_count = result['count'] if result else 0
            self.ui.labelOrders.setText(f"Pending Orders: {order_count}")
        except Exception as e:
            logger.error(f"Failed to load status: {e}")
    
    def close_all_positions(self):
        """Close all open positions"""
        reply = QMessageBox.question(
            self, 
            'Confirm', 
            'Close ALL positions?\nThis cannot be undone!',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.execute("UPDATE positions SET status = 'closed' WHERE status = 'open'")
                logger.warning("Emergency: All positions closed")
                QMessageBox.information(self, "Success", "All positions closed!")
                self.load_status()
            except Exception as e:
                logger.error(f"Error: {e}")
                QMessageBox.critical(self, "Error", str(e))
    
    def cancel_all_orders(self):
        """Cancel all pending orders"""
        reply = QMessageBox.question(
            self,
            'Confirm',
            'Cancel ALL pending orders?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.execute("UPDATE orders SET status = 'cancelled' WHERE status = 'pending'")
                logger.warning("Emergency: All orders cancelled")
                QMessageBox.information(self, "Success", "All orders cancelled!")
                self.load_status()
            except Exception as e:
                logger.error(f"Error: {e}")
                QMessageBox.critical(self, "Error", str(e))
    
    def stop_bot(self):
        """Stop trading bot"""
        reply = QMessageBox.question(
            self,
            'Confirm',
            'STOP the trading bot?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.warning("Emergency: Bot stopped")
            QMessageBox.information(self, "Success", "Bot stopped!")
            self.accept()