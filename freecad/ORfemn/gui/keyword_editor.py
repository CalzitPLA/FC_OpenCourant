"""Radioss Keyword Editor GUI for FreeCAD"""

import os
import html
import json
import datetime
import webbrowser

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

from .. import kfile_format
from .cache_viewer import CacheViewerWindow
from .template_editor import TemplateEditorDialog, load_active_templates

QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QSplitter = QtWidgets.QSplitter
QComboBox = QtWidgets.QComboBox
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QTextEdit = QtWidgets.QTextEdit
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QLabel = QtWidgets.QLabel
QFileDialog = QtWidgets.QFileDialog
QMessageBox = QtWidgets.QMessageBox
QMenuBar = QtWidgets.QMenuBar
QPushButton = QtWidgets.QPushButton
QLineEdit = QtWidgets.QLineEdit
QDialogButtonBox = QtWidgets.QDialogButtonBox
QTabWidget = QtWidgets.QTabWidget
QInputDialog = QtWidgets.QInputDialog
QWidget = QtWidgets.QWidget

MODULE_DIR = os.path.dirname(os.path.dirname(__file__))
SETTINGS_FILE = os.path.join(MODULE_DIR, 'keyword_editor_settings.json')

# Template modes and the template levels each one shows
TEMPLATE_MODES = {
    "minimal": ("minimal",),
    "basic": ("minimal", "basic"),
    "full": ("minimal", "basic", "full"),
}


def open_local_file(filepath):
    """Open a file with the desktop's default application."""
    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(filepath))


def open_url(url):
    """Open a URL in the system browser."""
    if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):
        webbrowser.open(url)


class KeywordEditorDialog(QtWidgets.QDialog):
    """Main dialog for the Radioss Keyword Editor."""

    def __init__(self, parent=None):
        super(KeywordEditorDialog, self).__init__(parent)
        self.setWindowTitle("Radioss Keyword Editor")
        self.setMinimumSize(1000, 700)

        self.current_keyword = None
        self.param_inputs = {}  # (card row, field index) -> QLineEdit
        self.param_defaults = {}  # (card row, field index) -> documented default
        self.card_rows = []  # [{'card': card definition, 'values': {field index: text}}]
        # Shared with the cache viewer; always modify in place, never rebind.
        self.keyword_cache = []
        self.cache_viewer = None
        self.template_editor = None

        self.template_mode = "full"
        self.load_settings()

        self.keywords = self.load_keywords()
        self.templates = self.load_templates()

        self.setup_ui()
        self.show_welcome_message()

        self.update_category_list()
        self.update_keyword_list()
        self.update_cache_display()

    # ------------------------------------------------------------------
    # Settings, keywords and templates
    # ------------------------------------------------------------------

    def load_settings(self):
        """Load user settings from file."""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                mode = settings.get('template_mode', 'full')
                self.template_mode = mode if mode in TEMPLATE_MODES else 'full'
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not load keyword editor settings: {e}\n")

    def save_settings(self):
        """Save user settings to file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({'template_mode': self.template_mode}, f, indent=2)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not save keyword editor settings: {e}\n")

    def load_keywords(self):
        """Load keywords from the JSON file with parameters (or the cleaned fallback)."""
        for filename in ('keywords_with_parameters.json', 'keywords_clean.json'):
            json_path = os.path.join(MODULE_DIR, filename)
            if not os.path.exists(json_path):
                continue
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                FreeCAD.Console.PrintError(f"Error loading keywords from {json_path}: {e}\n")
        FreeCAD.Console.PrintError("Keyword editor: no keyword database found\n")
        return []

    def load_templates(self):
        """Load the user's templates, or the shipped templates.json."""
        try:
            return load_active_templates()
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error loading templates: {e}\n")
            return {}

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def setup_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        menubar = QMenuBar()
        main_layout.setMenuBar(menubar)

        help_menu = menubar.addMenu("&Help")
        self.template_menu = menubar.addMenu("&Templates")
        examples_menu = menubar.addMenu("&Examples")

        help_menu.addAction("Search Help").triggered.connect(lambda: self.show_help_section("search_help"))
        help_menu.addAction("Tutorials").triggered.connect(lambda: self.show_help_section("tutorials"))
        help_menu.addAction("Reference Guide").triggered.connect(lambda: self.show_help_section("reference_guide"))

        self.update_template_menu()

        examples_menu.addAction("Latest Examples").triggered.connect(lambda: self.show_examples_section("latest"))
        examples_menu.addAction("Introductory Examples").triggered.connect(lambda: self.show_examples_section("introductory"))
        examples_menu.addAction("Implicit Examples").triggered.connect(lambda: self.show_examples_section("implicit"))
        examples_menu.addAction("OpenRadioss Examples").triggered.connect(lambda: self.show_examples_section("openradioss"))

        self.main_splitter = QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Left panel (navigation)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)
        left_layout.addWidget(self.category_combo)

        self.keywords_list = QListWidget()
        self.keywords_list.itemClicked.connect(self.on_keyword_selected)
        left_layout.addWidget(self.keywords_list)

        self.main_splitter.addWidget(left_panel)

        # Right panel (details)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)

        self.keyword_header = QLabel()
        self.keyword_header.setTextFormat(QtCore.Qt.RichText)
        self.keyword_header.setOpenExternalLinks(True)
        self.right_layout.addWidget(self.keyword_header)

        self.tab_widget = QTabWidget()

        self.desc_tab = QtWidgets.QTextBrowser()
        self.desc_tab.setOpenExternalLinks(True)  # documentation link opens in the browser
        self.tab_widget.addTab(self.desc_tab, "Description")

        # One row per card, one column per field (LS-DYNA cards have up to 8 fields)
        params_page = QWidget()
        params_layout = QVBoxLayout(params_page)
        params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_hint = QLabel()
        self.params_hint.setWordWrap(True)
        params_layout.addWidget(self.params_hint)
        self.params_tab = QTableWidget()
        self.params_tab.setColumnCount(kfile_format.FIELDS_PER_CARD)
        params_layout.addWidget(self.params_tab)
        params_buttons = QHBoxLayout()
        self.reset_fields_button = QPushButton("Reset to Defaults")
        self.reset_fields_button.setToolTip("Refill every field with its documented default value")
        self.reset_fields_button.clicked.connect(self.reset_fields)
        params_buttons.addWidget(self.reset_fields_button)
        self.clear_fields_button = QPushButton("Clear All Fields")
        self.clear_fields_button.clicked.connect(self.clear_fields)
        params_buttons.addWidget(self.clear_fields_button)
        self.repeat_card_button = QPushButton("Repeat Card")
        self.repeat_card_button.setToolTip("Add another line of the selected repeatable card (e.g. node lists)")
        self.repeat_card_button.clicked.connect(self.repeat_card)
        params_buttons.addWidget(self.repeat_card_button)
        self.remove_card_button = QPushButton("Remove Card")
        self.remove_card_button.setToolTip("Remove the selected extra line of a repeatable card")
        self.remove_card_button.clicked.connect(self.remove_card)
        params_buttons.addWidget(self.remove_card_button)
        # Follow the focused field so the card buttons match the card being edited
        QtWidgets.QApplication.instance().focusChanged.connect(self.update_card_buttons)
        self.params_tab.currentCellChanged.connect(self.update_card_buttons)
        params_buttons.addStretch()
        params_layout.addLayout(params_buttons)
        self.params_page = params_page
        self.tab_widget.addTab(params_page, "Parameters")

        self.generated_tab = QTextEdit()
        self.generated_tab.setReadOnly(True)
        self.tab_widget.addTab(self.generated_tab, "Generated Keyword")

        self.cache_tab = QTextEdit()
        self.cache_tab.setReadOnly(True)
        self.cache_tab_index = self.tab_widget.addTab(self.cache_tab, "Cached Keywords (0)")

        self.right_layout.addWidget(self.tab_widget)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setSizes([200, 600])

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self.generate_button = QPushButton("Generate Keyword")
        self.generate_button.clicked.connect(self.generate_keyword)
        button_box.addButton(self.generate_button, QDialogButtonBox.ActionRole)

        self.cache_button = QPushButton("Add to Cache")
        self.cache_button.clicked.connect(self.cache_keyword)
        self.cache_button.setEnabled(False)  # Enabled once a keyword is generated
        button_box.addButton(self.cache_button, QDialogButtonBox.ActionRole)

        self.update_file_button = QPushButton("Update .k File")
        self.update_file_button.clicked.connect(self.update_k_file)
        button_box.addButton(self.update_file_button, QDialogButtonBox.ActionRole)

        main_layout.addWidget(button_box)

    def update_template_menu(self):
        """(Re)build the template menu, showing only templates for the current mode."""
        self.template_menu.clear()
        levels = TEMPLATE_MODES[self.template_mode]

        previous_level = None
        for template_id, template in self.templates.items():
            level = template.get('level', 'full')
            if level not in levels:
                continue
            if previous_level is not None and level != previous_level:
                self.template_menu.addSeparator()
            previous_level = level
            action = self.template_menu.addAction(template.get('name', template_id))
            action.setToolTip(template.get('description', ''))
            action.triggered.connect(lambda checked=False, tid=template_id: self.load_template(tid))

        if previous_level is None:
            self.template_menu.addAction("No templates available").setEnabled(False)

        self.template_menu.addSeparator()
        self.template_menu.addAction("Edit Templates...").triggered.connect(self.open_template_editor)
        self.template_menu.addAction(f"Template Mode ({self.template_mode.title()})...").triggered.connect(
            self.configure_template_mode)

    def open_template_editor(self):
        """Open the template editor; the menu is rebuilt whenever templates are saved."""
        if self.template_editor is None:
            self.template_editor = TemplateEditorDialog(self)
            self.template_editor.templates_saved.connect(self.reload_templates)
        self.template_editor.show()
        self.template_editor.raise_()
        self.template_editor.activateWindow()

    def reload_templates(self):
        """Reload templates from disk and rebuild the template menu."""
        self.templates = self.load_templates()
        self.update_template_menu()

    def configure_template_mode(self):
        """Allow user to configure template mode."""
        modes = [m.title() for m in TEMPLATE_MODES]
        current_index = list(TEMPLATE_MODES).index(self.template_mode)

        mode, ok = QInputDialog.getItem(self, "Template Mode",
                                        "Select template complexity level:",
                                        modes, current_index, False)
        if ok:
            self.template_mode = mode.lower()
            self.update_template_menu()
            self.save_settings()

    def show_welcome_message(self):
        """Display welcome message in the details panel."""
        self.desc_tab.setHtml("""
        <div style="text-align: center; padding: 20px;">
            <h1>Welcome to Radioss Keyword Editor</h1>
            <p style="font-size: 14px; color: #666; margin-top: 20px;">
                This tool helps you manage and edit Radioss keywords for your simulations.
            </p>
            <div style="margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 5px; text-align: left;">
                <h3>Getting Started:</h3>
                <ul>
                    <li>Browse keywords using the list on the left</li>
                    <li>Filter by category using the dropdown menu</li>
                    <li>Fill in the fields on the Parameters tab and click "Generate Keyword"</li>
                    <li>Add generated keywords to the cache, or start from a template</li>
                    <li>Click "Update .k File" to write the cache into the FreeCAD document</li>
                </ul>
            </div>
        </div>
        """)
        self.keyword_header.setText("<h2>Welcome</h2>")
        self.params_tab.setRowCount(0)
        self.params_hint.setText("")
        self.reset_fields_button.setEnabled(False)
        self.clear_fields_button.setEnabled(False)
        self.repeat_card_button.setEnabled(False)
        self.remove_card_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Keyword browsing
    # ------------------------------------------------------------------

    def update_category_list(self):
        """Update the category dropdown with unique categories from keywords."""
        categories = {kw['category'] for kw in self.keywords if 'category' in kw}
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("All Categories")
        self.category_combo.addItems(sorted(categories))
        self.category_combo.blockSignals(False)

    def update_keyword_list(self):
        """Update the keyword list based on the selected category."""
        current_category = self.category_combo.currentText()
        self.keywords_list.clear()

        for kw in self.keywords:
            if current_category == "All Categories" or kw.get('category') == current_category:
                item = QListWidgetItem(kw.get('name', 'Unnamed'))
                item.setData(QtCore.Qt.UserRole, kw)
                self.keywords_list.addItem(item)

    def on_category_changed(self, index):
        """Handle category selection change."""
        self.update_keyword_list()

    def on_keyword_selected(self, item):
        """Show the selected keyword's details (the documentation link is in the description)."""
        if not item:
            return

        self.current_keyword = item.data(QtCore.Qt.UserRole)
        if not self.current_keyword:
            return

        self.show_keyword_details()

    def show_keyword_details(self):
        """Show details of the selected keyword."""
        if not self.current_keyword:
            self.show_welcome_message()
            return

        self.keyword_header.setText(
            f"{self.current_keyword.get('name', '')} - {self.current_keyword.get('category', '')}")
        self.desc_tab.setHtml(self.format_description(self.current_keyword))
        self.update_parameters_tab(self.current_keyword)
        self.generated_tab.clear()
        self.cache_button.setEnabled(False)

    @staticmethod
    def card_label(card):
        """Short label of a card's group, e.g. 'INERTIA', 'optional', 'repeatable'."""
        parts = list((card.get('options') or {}).values())
        if card.get('optional') and not parts:
            parts.append('optional')
        if card.get('repeat'):
            parts.append('repeatable')
        return ', '.join(parts)

    def format_description(self, kw):
        """Format the keyword description, documentation link and cards as HTML."""
        esc = html.escape
        name = esc(kw.get('name', 'Unknown'))
        category = esc(kw.get('category', 'Uncategorized'))
        description = esc(kw.get('description') or 'No description available.')
        doc_url = kw.get('documentation', '')

        text = f"""
        <div style="padding: 10px;">
            <h2>{name}</h2>
            <p><strong>Category:</strong> {category}</p>
        """
        if kw.get('keyword') and kw['keyword'] != kw.get('name'):
            text += f"<p><strong>Written as:</strong> <code>{esc(kw['keyword'])}</code></p>"
        if doc_url:
            text += (f'<p><strong>Documentation:</strong> '
                     f'<a href="{esc(doc_url, quote=True)}">{esc(doc_url)}</a></p>')
        text += f"<h3>Description</h3><p>{description}</p>"

        cards = kw.get('parameters') or []
        if cards:
            text += "<h3>Cards</h3>"
            previous_group = None
            for n, card in enumerate(cards, 1):
                if card.get('group') != previous_group and card.get('condition'):
                    text += f"<p><i>{esc(card['condition'])}</i></p>"
                previous_group = card.get('group')
                defaults = card.get('defaults', {})
                field_help = card.get('field_help', {})
                rows = ""
                for i in range(kfile_format.FIELDS_PER_CARD):
                    field = card.get(f'field_{i}', '')
                    if not field:
                        continue
                    key = f'field_{i}'
                    default = esc(defaults.get(key, ''))
                    rows += (f"<tr><td>{i + 1}</td><td><b>{esc(field)}</b></td>"
                             f"<td>{default}</td><td>{esc(field_help.get(key, ''))}</td></tr>")
                label = self.card_label(card)
                text += (f"<p><b>Card {n}</b>{' (' + esc(label) + ')' if label else ''}</p>"
                         '<table border="1" cellspacing="0" cellpadding="3">'
                         "<tr><th>#</th><th>Field</th><th>Default</th><th>Description</th></tr>"
                         f"{rows}</table>")

        text += "</div>"
        return text

    def update_parameters_tab(self, kw):
        """Show one row per card with an input for each named field.

        Fields of required cards are prefilled with their documented default;
        optional cards start empty (the default is shown greyed out) because
        filling in any field of an optional card group writes that group.
        """
        self.card_rows = []
        for card in kw.get('parameters') or []:
            defaults = card.get('defaults', {}) if not card.get('optional') else {}
            self.card_rows.append({'card': card, 'values': {
                i: defaults.get(f'field_{i}', '') for i in range(kfile_format.FIELDS_PER_CARD)}})
        self._render_card_rows()

    def _sync_card_values(self):
        """Copy the current input texts back into self.card_rows."""
        for (row, col), value_input in self.param_inputs.items():
            if row < len(self.card_rows):
                self.card_rows[row]['values'][col] = value_input.text()

    def _render_card_rows(self):
        """(Re)build the parameter table from self.card_rows."""
        self.params_tab.clear()
        self.param_inputs = {}
        self.param_defaults = {}
        rows = self.card_rows

        self.params_tab.setRowCount(len(rows))
        self.params_tab.setHorizontalHeaderLabels(
            [f"Field {i + 1}" for i in range(kfile_format.FIELDS_PER_CARD)])

        used_columns = 0
        card_numbers = {}
        for row, row_data in enumerate(rows):
            card = row_data['card']
            number = card_numbers.setdefault(id(card), len(card_numbers) + 1)
            label = self.card_label(card)
            header = QTableWidgetItem(f"Card {number}" + (f"\n{label}" if label else ""))
            header.setToolTip(card.get('condition', '') or "Required card")
            self.params_tab.setVerticalHeaderItem(row, header)

            defaults = card.get('defaults', {})
            field_help = card.get('field_help', {})
            for col in range(kfile_format.FIELDS_PER_CARD):
                key = f'field_{col}'
                field_name = card.get(key, '')
                if not field_name:
                    # Unused column: keep it so later fields stay in position
                    blank = QTableWidgetItem("")
                    blank.setFlags(QtCore.Qt.NoItemFlags)
                    self.params_tab.setItem(row, col, blank)
                    continue
                used_columns = max(used_columns, col + 1)
                cell = QWidget()
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(2, 1, 2, 1)
                cell_layout.setSpacing(0)
                name_label = QLabel(field_name)
                name_label.setStyleSheet("font-size: 9pt; color: palette(mid);")
                cell_layout.addWidget(name_label)
                value_input = QLineEdit(row_data['values'].get(col, ''))
                default = defaults.get(key, '')
                value_input.setPlaceholderText(f"{default} (default)" if default else field_name)
                tooltip = field_name
                if field_help.get(key):
                    tooltip += f"\n{field_help[key]}"
                cell.setToolTip(tooltip)
                value_input.setToolTip(tooltip)
                cell_layout.addWidget(value_input)
                self.params_tab.setCellWidget(row, col, cell)
                self.param_inputs[(row, col)] = value_input
                self.param_defaults[(row, col)] = '' if card.get('optional') else default

        for col in range(kfile_format.FIELDS_PER_CARD):
            self.params_tab.setColumnHidden(col, col >= max(used_columns, 1))
        self.params_tab.resizeColumnsToContents()
        self.params_tab.resizeRowsToContents()

        n_defaults = sum(1 for value in self.param_defaults.values() if value)
        if rows:
            self.params_hint.setText(
                f"{len(self.param_inputs)} fields, {n_defaults} prefilled with their documented default. "
                "Optional cards are only written when you fill them in; the keyword gets their option "
                "suffix (e.g. _INERTIA). Hover a field or card for details.")
        else:
            self.params_hint.setText("This keyword has no cards; \"Generate Keyword\" writes the keyword line only.")
        self.reset_fields_button.setEnabled(bool(self.param_inputs))
        self.clear_fields_button.setEnabled(bool(self.param_inputs))
        self.update_card_buttons()

    def _selected_row(self):
        """Row of the focused field input, or the table's current row."""
        for (row, _col), value_input in self.param_inputs.items():
            if value_input.hasFocus():
                return row
        return self.params_tab.currentRow()

    def update_card_buttons(self, *_args):
        row = self._selected_row() if self.card_rows else -1
        card = self.card_rows[row]['card'] if 0 <= row < len(self.card_rows) else None
        repeatable = bool(card and card.get('repeat'))
        self.repeat_card_button.setEnabled(repeatable)
        copies = sum(1 for r in self.card_rows if card is not None and r['card'] is card)
        self.remove_card_button.setEnabled(repeatable and copies > 1)

    def repeat_card(self):
        """Add another instance of the selected repeatable card below it."""
        row = self._selected_row()
        if not 0 <= row < len(self.card_rows) or not self.card_rows[row]['card'].get('repeat'):
            return
        self._sync_card_values()
        card = self.card_rows[row]['card']
        self.card_rows.insert(row + 1, {'card': card, 'values': {}})
        self._render_card_rows()
        first_input = next((w for (r, _c), w in sorted(self.param_inputs.items()) if r == row + 1), None)
        if first_input:
            first_input.setFocus()

    def remove_card(self):
        """Remove the selected extra instance of a repeatable card."""
        row = self._selected_row()
        if not 0 <= row < len(self.card_rows):
            return
        card = self.card_rows[row]['card']
        if not card.get('repeat') or sum(1 for r in self.card_rows if r['card'] is card) < 2:
            return
        self._sync_card_values()
        del self.card_rows[row]
        self._render_card_rows()

    def reset_fields(self):
        """Refill all fields with their documented defaults (optional cards are emptied)."""
        for key, value_input in self.param_inputs.items():
            value_input.setText(self.param_defaults.get(key, ''))

    def clear_fields(self):
        """Empty all fields."""
        for value_input in self.param_inputs.values():
            value_input.clear()

    # ------------------------------------------------------------------
    # Keyword generation and cache
    # ------------------------------------------------------------------

    def generate_keyword(self):
        """Generate keyword text from the field inputs."""
        if not self.current_keyword:
            QMessageBox.warning(self, "No Keyword Selected", "Please select a keyword first.")
            return

        self._sync_card_values()
        cards = []
        for row_data in self.card_rows:
            card = row_data['card']
            cards.append({
                'values': [row_data['values'].get(col, '') if card.get(f'field_{col}') else ''
                           for col in range(kfile_format.FIELDS_PER_CARD)],
                'group': card.get('group', 0),
                'optional': card.get('optional', False),
                'options': card.get('options') or {},
            })
        keyword = self.current_keyword.get('keyword') or self.current_keyword.get('name', '')
        keyword_text = kfile_format.build_keyword(keyword, cards)

        self.generated_tab.setPlainText(keyword_text)
        self.tab_widget.setCurrentWidget(self.generated_tab)
        self.cache_button.setEnabled(True)

    def _make_cache_entry(self, keyword_name, text):
        return {
            'text': text,
            'timestamp': datetime.datetime.now().strftime("%H:%M:%S"),
            'keyword_name': keyword_name,
        }

    def cache_keyword(self):
        """Cache the currently generated keyword."""
        keyword_text = self.generated_tab.toPlainText().rstrip()
        if not keyword_text:
            QMessageBox.warning(self, "No Generated Keyword",
                                "Please generate a keyword first before caching it.")
            return

        # Name the entry after the keyword actually written (e.g. *PART_INERTIA)
        keyword_name = keyword_text.splitlines()[0].strip()
        self.keyword_cache.append(self._make_cache_entry(keyword_name, keyword_text))
        self.update_cache_display()
        self.open_cache_viewer()

    def load_template(self, template_id):
        """Replace the keyword cache with the keywords of a template."""
        template = self.templates.get(template_id)
        if not template or not template.get('keywords'):
            QMessageBox.warning(self, "Template Error", "Template contains no keywords.")
            return

        if self.keyword_cache:
            reply = QMessageBox.question(
                self, "Load Template",
                f"Loading '{template.get('name', template_id)}' replaces the "
                f"{len(self.keyword_cache)} cached keywords. Continue?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        entries = []
        for kw_data in template['keywords']:
            text = kfile_format.template_keyword_text(kw_data)
            if text:
                entries.append(self._make_cache_entry(kw_data['name'], text))
        self.keyword_cache[:] = entries

        self.update_cache_display()
        self.tab_widget.setCurrentWidget(self.cache_tab)

    def update_cache_display(self):
        """Update the cached keywords tab and an open cache viewer."""
        self.tab_widget.setTabText(self.cache_tab_index, f"Cached Keywords ({len(self.keyword_cache)})")

        if not self.keyword_cache:
            self.cache_tab.setPlainText("No keywords cached yet.\n\nGenerate a keyword and click 'Add to Cache', "
                                        "or load a template from the Templates menu.")
        else:
            self.cache_tab.setPlainText(self._generate_complete_k_file())

        if self.cache_viewer is not None and self.cache_viewer.isVisible():
            self.cache_viewer.update_display()

    def open_cache_viewer(self):
        """Open the cache viewer window."""
        if self.cache_viewer is None:
            self.cache_viewer = CacheViewerWindow(self.keyword_cache, self)
        self.cache_viewer.update_display()
        self.cache_viewer.show()
        self.cache_viewer.raise_()
        self.cache_viewer.activateWindow()

    def _generate_complete_k_file(self):
        """Generate complete .k file content from cached keywords."""
        return kfile_format.build_k_file(
            [(entry['keyword_name'], entry['text']) for entry in self.keyword_cache])

    def update_k_file(self):
        """Write the cached keywords into a text object of the active document."""
        if not self.keyword_cache:
            QMessageBox.warning(self, "No Cached Keywords",
                                "No keywords in cache. Generate and cache some keywords first.")
            return

        doc = FreeCAD.ActiveDocument
        if not doc:
            QMessageBox.warning(self, "No Active Document",
                                "Please open or create a FreeCAD document first.")
            return

        try:
            k_file_content = self._generate_complete_k_file()

            k_text_object = None
            for obj in doc.Objects:
                if obj.TypeId == 'App::TextDocument' and obj.Label.startswith("LS-DYNA_k_File"):
                    k_text_object = obj
                    break

            if k_text_object is None:
                k_text_object = doc.addObject("App::TextDocument", "LS-DYNA_k_File")
            k_text_object.Label = f"LS-DYNA_k_File_{len(self.keyword_cache)}_keywords"
            k_text_object.Text = k_file_content
            doc.recompute()

            QMessageBox.information(self, "Document Updated",
                                    f"LS-DYNA .k file content updated in document object:\n'{k_text_object.Label}'\n\n"
                                    f"Includes {len(self.keyword_cache)} cached keywords.")

            reply = QMessageBox.question(self, "Save to File",
                                         "Do you also want to save the .k file to an external file?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._save_k_file_to_disk(k_file_content)

        except Exception as e:
            QMessageBox.critical(self, "Update Error",
                                 f"Failed to update document object:\n{str(e)}")

    def _save_k_file_to_disk(self, k_file_content):
        """Save .k file content to external file."""
        default_filename = f"updated_model_{len(self.keyword_cache)}_keywords.k"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save .k File to Disk",
            os.path.join(os.path.expanduser("~"), default_filename),
            "LS-DYNA files (*.k);;All files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w') as f:
                f.write(k_file_content)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save .k file:\n{str(e)}")
            return

        reply = QMessageBox.question(self, "File Saved",
                                     f".k file saved successfully:\n{filepath}\n\nDo you want to open it?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            open_local_file(filepath)

    # ------------------------------------------------------------------
    # Documentation and examples
    # ------------------------------------------------------------------

    def show_help_section(self, section_name):
        """Show a specific help section of the Radioss LS-DYNA input reference."""
        base_url = "https://2021.help.altair.com/2021/hwsolvers/rad/topics/solvers/rad"

        section_map = {
            "search_help": "search_help_lsdyna_r.htm",
            "whats_new": "whats_new_lsdyna_r.htm",
            "overview": "overview_lsdyna_r.htm",
            "tutorials": "tutorials_lsdyna_r.htm",
            "user_guide": "user_guide_lsdyna_r.htm",
            "reference_guide": "reference_guide_lsdyna_r.htm",
            "example_guide": "example_guide_lsdyna_r.htm",
            "verification": "verification_problems_lsdyna_r.htm",
            "faq": "faq_lsdyna_r.htm",
            "theory": "theory_manual_lsdyna_r.htm",
            "subroutines": "user_subroutines_lsdyna_r.htm",
            "starter": "starter_input_lsdyna_r.htm",
            "engine": "engine_input_lsdyna_r.htm",
            "index": "index_lsdyna_r.htm"
        }

        if section_name in section_map:
            open_url(f"{base_url}/{section_map[section_name]}#ls-dyna-input-beta")

    def show_examples_section(self, section):
        """Open an examples section of dynaexamples.com in the browser."""
        base_url = "https://www.dynaexamples.com"

        section_urls = {
            "latest": "/latest-examples",
            "introductory": "/introduction",
            "implicit": "/implicit",
            "thermal": "/thermal",
            "structural": "/implicit",
            "fluid": "/icfd",
            "ale": "/ale-s-ale",
            "em": "/em",
            "cese": "/cese",
            "openradioss": "/Example+LS-DYNA+Format+Models"
        }

        if section in section_urls:
            url = base_url + section_urls[section]
            open_url(url)
