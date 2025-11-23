"""Exchange Selector Dialog"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt


class ExchangeSelectorDialog(QDialog):
    """Dialog to select which exchange to configure"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Exchange")
        self.setModal(True)
        self.resize(300, 250)
        
        self.selected_exchange = None
        
        # Layout
        layout = QVBoxLayout()
        
        # Label
        label = QLabel("Select an exchange to configure API keys:")
        layout.addWidget(label)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.addItems([
            "Binance",
            "Bybit",
            "KuCoin",
            "MEXC",
            "OKX"
        ])
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
        btn_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def get_selected_exchange(self):
        """Get selected exchange name"""
        item = self.list_widget.currentItem()
        if item:
            return item.text().lower()
        return None