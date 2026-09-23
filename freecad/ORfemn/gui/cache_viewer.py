"""Window for viewing and managing cached LS-DYNA keywords."""

from PySide import QtCore, QtWidgets


class CacheViewerWindow(QtWidgets.QDialog):
    """Window for viewing and managing cached LS-DYNA keywords.

    ``keyword_cache`` is shared with the keyword editor (same list object),
    so changes made here are visible there and vice versa.
    """

    def __init__(self, keyword_cache, parent=None):
        super(CacheViewerWindow, self).__init__(parent)
        self.keyword_cache = keyword_cache
        self.parent_editor = parent
        self.setWindowTitle("LS-DYNA Keyword Cache Viewer")
        self.setMinimumSize(900, 700)
        self.setModal(False)

        self.setup_ui()
        self.update_display()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)

        title_label = QtWidgets.QLabel("LS-DYNA Keyword Cache")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("font-size: 12px; color: #666; margin: 5px;")
        layout.addWidget(self.info_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        self.cache_list = QtWidgets.QListWidget()
        self.cache_list.setMaximumHeight(200)
        self.cache_list.currentItemChanged.connect(self.show_keyword_details)
        splitter.addWidget(self.cache_list)

        self.content_text = QtWidgets.QTextEdit()
        self.content_text.setReadOnly(True)
        splitter.addWidget(self.content_text)

        layout.addWidget(splitter)

        button_layout = QtWidgets.QHBoxLayout()

        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.update_display)
        button_layout.addWidget(self.refresh_button)

        self.remove_button = QtWidgets.QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.remove_selected)
        button_layout.addWidget(self.remove_button)

        self.clear_all_button = QtWidgets.QPushButton("Clear All")
        self.clear_all_button.clicked.connect(self.clear_all)
        button_layout.addWidget(self.clear_all_button)

        button_layout.addStretch()

        self.generate_k_button = QtWidgets.QPushButton("Generate .k File")
        self.generate_k_button.clicked.connect(self.generate_k_file)
        self.generate_k_button.setEnabled(hasattr(self.parent_editor, 'update_k_file'))
        button_layout.addWidget(self.generate_k_button)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def update_display(self):
        """Update the cache display."""
        self.cache_list.clear()
        self.info_label.setText(f"Total cached keywords: {len(self.keyword_cache)}")

        if not self.keyword_cache:
            self.content_text.setPlainText("No keywords cached yet.\n\nGenerate a keyword and click 'Add to Cache' to start building your .k file.")
            return

        for i, entry in enumerate(self.keyword_cache, 1):
            item = QtWidgets.QListWidgetItem(f"{i}. {entry['keyword_name']} ({entry['timestamp']})")
            item.setData(QtCore.Qt.UserRole, entry)
            self.cache_list.addItem(item)

        self.cache_list.setCurrentRow(self.cache_list.count() - 1)

    def show_keyword_details(self, item, _previous=None):
        """Show details of the selected cached keyword."""
        if not item:
            return

        entry = item.data(QtCore.Qt.UserRole)
        if not entry:
            return

        content = f"Keyword: {entry['keyword_name']}\n"
        content += f"Timestamp: {entry['timestamp']}\n"
        content += "=" * 50 + "\n\n"
        content += entry['text']

        self.content_text.setPlainText(content)

    def _notify_editor(self):
        if self.parent_editor and hasattr(self.parent_editor, 'update_cache_display'):
            self.parent_editor.update_cache_display()

    def remove_selected(self):
        """Remove the selected cached keyword."""
        current_row = self.cache_list.currentRow()
        if current_row < 0:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Please select a keyword to remove.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Remove Keyword",
            "Are you sure you want to remove this keyword from the cache?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes and 0 <= current_row < len(self.keyword_cache):
            self.keyword_cache.pop(current_row)
            self._notify_editor()
            self.update_display()

    def clear_all(self):
        """Clear all cached keywords."""
        if not self.keyword_cache:
            QtWidgets.QMessageBox.information(self, "Cache Empty",
                                              "No keywords in cache to clear.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Clear All Keywords",
            f"Are you sure you want to clear all {len(self.keyword_cache)} cached keywords?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self.keyword_cache.clear()
            self._notify_editor()
            self.update_display()

    def generate_k_file(self):
        """Generate .k file from current cache."""
        if not self.keyword_cache:
            QtWidgets.QMessageBox.warning(self, "No Keywords",
                                          "No keywords in cache to generate file from.")
            return

        if self.parent_editor and hasattr(self.parent_editor, 'update_k_file'):
            self.parent_editor.update_k_file()
